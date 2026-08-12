"""MCP-транспорт для доверенного ядра elemspec-agent.

Сервер не содержит доменной логики: он публикует узкие MCP-инструменты
и передаёт вызовы существующему Python API. Живая browser-разведка изолирована
в фиксированном дочернем процессе ``elemspec-agent browser``.
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import __version__
from .agent import (
    ВЕРСИЯ_API,
    ОшибкаАгентскогоAPI,
    контракт,
    проверить_тест,
    проверить_черновик,
)
from .agent_gaps import зарегистрировать
from .agent_prompt import новый_тест_prompt
from .agent_proof import доказать_красный
from .agent_sessions import применить, подготовить, открыть_сессию
from .project import ПолитикаХостов, Проект


ВЕРСИЯ_MCP_API = "0.7.0-dev.0"


def корень_mcp(явный: Path | None = None) -> Path:
    """Определить проект из аргумента, окружения клиента или cwd."""
    return явный or Path(
        os.environ.get("ELEMSPEC_PROJECT")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or Path.cwd()
    )


ТАЙМАУТ_BROWSER_С = 90
ИМЕНА_MCP_ИНСТРУМЕНТОВ = (
    "get_contract",
    "validate_test",
    "validate_draft",
    "start_session",
    "prepare_draft",
    "apply_draft",
    "prove_test",
    "register_engine_gap",
    "browser_start",
    "browser_action",
    "browser_close",
)


class ОшибкаMCPАдаптера(ОшибкаАгентскогоAPI):
    """MCP-вызов нарушил порядок операций агентского ядра."""


class _BrowserProcess:
    def __init__(self, корень: Path) -> None:
        self._lock = threading.Lock()
        self._process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "elemspec.agent_cli",
                "--project",
                str(корень),
                "browser",
            ],
            cwd=корень,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
        )
        self._ответы: queue.Queue[str | None] = queue.Queue()
        self._reader = threading.Thread(target=self._читать_stdout, daemon=True)
        self._reader.start()

    def _читать_stdout(self) -> None:
        assert self._process.stdout is not None
        for строка in self._process.stdout:
            self._ответы.put(строка)
        self._ответы.put(None)

    def вызвать(self, запрос: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._process.poll() is not None:
                raise ОшибкаMCPАдаптера(
                    "browser-сессия аварийно завершилась"
                )
            assert self._process.stdin is not None
            assert self._process.stdout is not None
            self._process.stdin.write(
                json.dumps(запрос, ensure_ascii=False) + "\n"
            )
            self._process.stdin.flush()
            try:
                строка = self._ответы.get(timeout=ТАЙМАУТ_BROWSER_С)
            except queue.Empty:
                raise ОшибкаMCPАдаптера(
                    f"browser-операция не завершилась за {ТАЙМАУТ_BROWSER_С} с"
                ) from None
            if строка is None:
                raise ОшибкаMCPАдаптера(
                    "browser-сессия закрыла stdout без ответа"
                )
            try:
                ответ = json.loads(строка)
            except json.JSONDecodeError as ошибка:
                raise ОшибкаMCPАдаптера(
                    "browser-сессия вернула некорректный JSON"
                ) from ошибка
            if not ответ.get("успех"):
                raise ОшибкаMCPАдаптера(
                    str(ответ.get("ошибка", "неизвестная browser-ошибка"))
                )
            return ответ

    def закрыть(self) -> None:
        if self._process.poll() is not None:
            return
        try:
            self.вызвать({"операция": "close"})
            self._process.wait(timeout=10)
        except Exception:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)


class MCPRuntime:
    """Проектные пути и живые browser-процессы одного MCP-сервера."""

    def __init__(self, корень: Path, optional_project: bool = False) -> None:
        self._старт = корень
        self._проект: Проект | None = None
        if not optional_project:
            self._найти_проект()
        self._browsers: dict[str, _BrowserProcess] = {}
        self._lock = threading.Lock()

    def _найти_проект(self) -> Проект:
        if self._проект is None:
            self._проект = Проект.найти(self._старт)
        return self._проект

    @property
    def корень(self) -> Path:
        return self._найти_проект().корень

    @property
    def тесты(self) -> Path:
        return self._найти_проект().тесты

    @property
    def сессии(self) -> Path:
        проект = self._найти_проект()
        return проект.состояние / "sessions"

    @property
    def разведки(self) -> Path:
        проект = self._найти_проект()
        return проект.состояние / "discoveries"

    @property
    def отчёты(self) -> Path:
        return self._найти_проект().отчёты

    @property
    def политика(self) -> ПолитикаХостов:
        return self._найти_проект().политика

    def начать_browser(self, url: str) -> dict[str, Any]:
        id_сессии = str(uuid.uuid4())
        процесс = _BrowserProcess(self.корень)
        try:
            ответ = процесс.вызвать({"операция": "start", "url": url})
        except Exception:
            процесс.закрыть()
            raise
        with self._lock:
            self._browsers[id_сессии] = процесс
        return {"browser_session": id_сессии, **ответ}

    def browser(self, id_сессии: str, запрос: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            процесс = self._browsers.get(id_сессии)
        if процесс is None:
            raise ОшибкаMCPАдаптера(
                f"browser-сессия '{id_сессии}' не найдена или закрыта"
            )
        return процесс.вызвать(запрос)

    def закрыть_browser(self, id_сессии: str) -> dict[str, Any]:
        with self._lock:
            процесс = self._browsers.pop(id_сессии, None)
        if процесс is None:
            raise ОшибкаMCPАдаптера(
                f"browser-сессия '{id_сессии}' не найдена или закрыта"
            )
        процесс.закрыть()
        return {"закрыт": True, "browser_session": id_сессии}

    def закрыть(self) -> None:
        with self._lock:
            процессы = list(self._browsers.values())
            self._browsers.clear()
        for процесс in процессы:
            процесс.закрыть()


def _ответ(результат: dict[str, Any]) -> dict[str, Any]:
    return {
        "mcp_api_version": ВЕРСИЯ_MCP_API,
        "agent_api_version": ВЕРСИЯ_API,
        "elemspec_version": __version__,
        "result": результат,
    }


def создать_mcp(среда: MCPRuntime) -> MCPServer:
    """Создать MCP-сервер, привязанный к одному проекту elemspec."""
    сервер = MCPServer(
        "elemspec-agent",
        version=__version__,
        # Клиенты без меню MCP prompts всё равно получают тот же строгий процесс
        # через стандартное поле ServerCapabilities.instructions.
        instructions=новый_тест_prompt(),
    )
    чтение = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    запись = ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
    browser = ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )

    @сервер.prompt(
        name="new_test",
        title="Новый UI-тест ElemSpec",
        description=(
            "Преобразовать сценарий на естественном языке в исследованный, "
            "валидированный и доказанный feature-тест ElemSpec"
        ),
    )
    def новый_тест(сценарий: str = "") -> str:
        return новый_тест_prompt(сценарий)

    @сервер.tool(annotations=чтение)
    def get_contract() -> dict[str, Any]:
        """Get DSL phrases, versions, allowed hosts, tests, and workflow contract."""
        return _ответ(контракт(среда.тесты, среда.политика))

    @сервер.tool(annotations=чтение)
    def validate_test(test_name: str) -> dict[str, Any]:
        """Statically validate one existing test selected by simple directory name."""
        return _ответ(проверить_тест(среда.тесты, test_name, среда.политика))

    @сервер.tool(annotations=чтение)
    def validate_draft(test_name: str, init_json: str, feature: str) -> dict[str, Any]:
        """Validate an in-memory init.json and Russian Gherkin draft without writing."""
        return _ответ(
            проверить_черновик(test_name, init_json, feature, среда.политика)
        )

    @сервер.tool(annotations=запись)
    def start_session(test_name: str) -> dict[str, Any]:
        """Start a write-scoped session for exactly one new or existing test."""
        return _ответ(открыть_сессию(среда.тесты, среда.сессии, test_name))

    @сервер.tool(annotations=запись)
    def prepare_draft(
        session_id: str,
        discovery_id: str,
        init_json: str,
        feature: str,
    ) -> dict[str, Any]:
        """Bind a draft to browser evidence, validate it, and prepare/apply its diff."""
        return _ответ(
            подготовить(
                среда.тесты,
                среда.сессии,
                session_id,
                init_json,
                feature,
                среда.политика,
                среда.разведки,
                discovery_id,
            )
        )

    @сервер.tool(annotations=запись)
    def apply_draft(
        session_id: str,
        draft_revision: str,
        confirm_bug: bool = False,
    ) -> dict[str, Any]:
        """Apply one exact prepared revision; confirm_bug requires the author's decision."""
        return _ответ(
            применить(
                среда.тесты,
                среда.сессии,
                session_id,
                draft_revision,
                confirm_bug,
            )
        )

    @сервер.tool(annotations=запись)
    def prove_test(session_id: str) -> dict[str, Any]:
        """Prove applied test green-red-green or reproduce an explicitly confirmed bug."""
        return _ответ(
            доказать_красный(среда.тесты, среда.сессии, среда.отчёты, session_id)
        )

    @сервер.tool(annotations=запись)
    def register_engine_gap(session_id: str, gap: dict[str, Any]) -> dict[str, Any]:
        """Register a structured engine gap linked from the active test draft."""
        return _ответ(зарегистрировать(среда.корень, среда.сессии, session_id, gap))

    @сервер.tool(annotations=browser)
    def browser_start(url: str) -> dict[str, Any]:
        """Start isolated live discovery at an allowlisted URL; returns session/evidence IDs."""
        return _ответ(среда.начать_browser(url))

    @сервер.tool(annotations=browser)
    def browser_action(
        browser_session: str,
        operation: Literal[
            "snapshot",
            "locator-check",
            "locator-pick",
            "table-row-check",
            "table-row-open",
            "click",
            "hover",
            "fill",
            "select-value",
            "select-any-value",
            "read-value",
            "key",
        ],
        ref: str | None = None,
        locator_kind: Literal[
            "элемент", "поле", "команда", "команда диалога", "пункт навигации",
            "заголовок формы", "заголовок диалога", "текст", "селектор"
        ] | None = None,
        value: str | None = None,
        table: str | None = None,
        column: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        """Run one constrained action in an existing discovery browser session."""
        if operation == "locator-check" and (locator_kind is None or value is None):
            raise ОшибкаMCPАдаптера(
                "locator-check требует locator_kind и value"
            )
        if operation in {"table-row-check", "table-row-open"} and (
            table is None or column is None or value is None
        ):
            raise ОшибкаMCPАдаптера(
                f"{operation} требует table, column и value"
            )
        if (
            operation
            in {
                "locator-pick", "click", "hover", "fill", "select-value",
                "select-any-value",
                "read-value",
            }
            and ref is None
        ):
            raise ОшибкаMCPАдаптера(
                f"{operation} требует ref из browser snapshot"
            )
        if operation in {"fill", "select-value", "select-any-value", "key"} and value is None:
            raise ОшибкаMCPАдаптера(f"{operation} требует value")
        if not 1 <= limit <= 2000:
            raise ОшибкаMCPАдаптера("limit должен быть от 1 до 2000")
        запрос: dict[str, Any] = {"операция": operation}
        if operation == "snapshot":
            запрос["лимит"] = limit
        elif operation == "locator-check":
            запрос.update({"вид": locator_kind, "значение": value})
        elif operation in {"table-row-check", "table-row-open"}:
            запрос.update(
                {"таблица": table, "колонка": column, "значение": value}
            )
        elif operation in {"locator-pick", "click", "hover", "read-value"}:
            запрос["ref"] = ref
        elif operation in {"fill", "select-value", "select-any-value"}:
            запрос.update({"ref": ref, "значение": value})
        else:
            запрос["клавиша"] = value
        return _ответ(среда.browser(browser_session, запрос))

    @сервер.tool(annotations=browser)
    def browser_close(browser_session: str) -> dict[str, Any]:
        """Close one live discovery browser session and release its process."""
        return _ответ(среда.закрыть_browser(browser_session))

    return сервер


def main(аргументы: list[str] | None = None) -> int:
    import argparse

    парсер = argparse.ArgumentParser(prog="elemspec-mcp")
    парсер.add_argument("--project", type=Path)
    парсер.add_argument("--optional-project", action="store_true")
    опции = парсер.parse_args(аргументы)
    среда = MCPRuntime(
        корень_mcp(опции.project), optional_project=опции.optional_project
    )
    сервер = создать_mcp(среда)
    atexit.register(среда.закрыть)
    сервер.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
