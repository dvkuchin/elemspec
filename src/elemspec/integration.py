"""Пользовательские интеграции ElemSpec с ИИ-агентами."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from importlib.resources import files
from pathlib import Path
from typing import Any

from . import __version__


class ОшибкаИнтеграции(RuntimeError):
    """Интеграцию нельзя безопасно установить или проверить."""


def _codex_home() -> Path:
    значение = os.environ.get("CODEX_HOME")
    return Path(значение).expanduser() if значение else Path.home() / ".codex"


def _codex() -> str:
    найден = shutil.which("codex")
    if найден:
        return найден
    macos = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
    if macos.is_file():
        return str(macos)
    raise ОшибкаИнтеграции(
        "Codex CLI не найден; установите Codex или ChatGPT desktop"
    )


def _источник_skill() -> Path:
    путь = Path(str(files("elemspec").joinpath("resources/skill/new-test")))
    if not (путь / "SKILL.md").is_file():
        raise ОшибкаИнтеграции(f"skill $new-test не включён в пакет: {путь}")
    return путь


def _маркер(каталог: Path) -> Path:
    return каталог / ".elemspec-managed.json"


def _наш_skill(каталог: Path) -> bool:
    файл = _маркер(каталог)
    if not файл.is_file():
        return False
    try:
        данные = json.loads(файл.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return данные.get("managed_by") == "elemspec" and данные.get("skill") == "new-test"


def _подготовить_skill(временный: Path) -> None:
    shutil.copytree(_источник_skill(), временный)
    _маркер(временный).write_text(
        json.dumps(
            {
                "managed_by": "elemspec",
                "skill": "new-test",
                "elemspec_version": __version__,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _удалить_путь(путь: Path) -> None:
    if путь.is_symlink() or путь.is_file():
        путь.unlink()
    elif путь.exists():
        shutil.rmtree(путь)


def _установить_skill(цель: Path, force: bool) -> None:
    цель.parent.mkdir(parents=True, exist_ok=True)
    if (цель.exists() or цель.is_symlink()) and not (_наш_skill(цель) or force):
        raise ОшибкаИнтеграции(
            f"{цель} уже существует и не помечен как установка ElemSpec; "
            "проверьте его или повторите с --force"
        )

    временный = Path(tempfile.mkdtemp(prefix=".new-test-", dir=цель.parent))
    временный.rmdir()
    резерв = цель.parent / f".new-test-backup-{uuid.uuid4().hex}"
    try:
        _подготовить_skill(временный)
        if цель.exists() or цель.is_symlink():
            цель.rename(резерв)
        временный.rename(цель)
    except Exception:
        if (
            not (цель.exists() or цель.is_symlink())
            and (резерв.exists() or резерв.is_symlink())
        ):
            резерв.rename(цель)
        raise
    finally:
        _удалить_путь(временный)
        _удалить_путь(резерв)


def _удалить_skill(цель: Path, force: bool) -> None:
    if not (цель.exists() or цель.is_symlink()):
        return
    if not (_наш_skill(цель) or force):
        raise ОшибкаИнтеграции(
            f"{цель} не помечен как установка ElemSpec; "
            "проверьте его или повторите с --force"
        )
    _удалить_путь(цель)


def _прочитать_mcp(codex: str) -> dict[str, Any] | None:
    процесс = subprocess.run(
        [codex, "mcp", "get", "elemspec", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if процесс.returncode == 0:
        try:
            return json.loads(процесс.stdout)
        except json.JSONDecodeError as ошибка:
            raise ОшибкаИнтеграции(
                "Codex вернул некорректный JSON для MCP elemspec"
            ) from ошибка
    вывод = f"{процесс.stdout}\n{процесс.stderr}"
    if "No MCP server named 'elemspec' found" in вывод:
        return None
    raise ОшибкаИнтеграции(
        f"не удалось прочитать MCP-конфигурацию Codex: {вывод.strip()}"
    )


def _команда_mcp(проект: Path | None = None) -> tuple[str, list[str]]:
    # Нельзя resolve(): bin/python в venv/pipx часто является symlink на системный
    # Python, а MCP должен запускаться именно внутри окружения с пакетом ElemSpec.
    аргументы = ["-m", "elemspec"]
    if проект is not None:
        аргументы.extend(["--project", str(проект.expanduser().resolve())])
    аргументы.append("mcp")
    if проект is None:
        аргументы.append("--optional-project")
    return str(Path(sys.executable).absolute()), аргументы


def конфигурация_mcp(проект: Path | None = None) -> dict[str, Any]:
    """Вернуть переносимый JSON-блок для интерфейса локального MCP-клиента."""
    команда, аргументы = _команда_mcp(проект)
    return {
        "mcpServers": {
            "elemspec": {
                "type": "stdio",
                "command": команда,
                "args": аргументы,
            }
        }
    }


def _наш_mcp(данные: dict[str, Any] | None, проект: Path | None = None) -> bool:
    if данные is None:
        return False
    transport = данные.get("transport", {})
    команда, аргументы = _команда_mcp(проект)
    return (
        transport.get("type") == "stdio"
        and transport.get("command") == команда
        and transport.get("args") == аргументы
    )


def _установить_mcp(
    codex: str, force: bool, проект: Path | None = None
) -> None:
    существующий = _прочитать_mcp(codex)
    if _наш_mcp(существующий, проект):
        return
    if существующий is not None and not force:
        raise ОшибкаИнтеграции(
            "MCP-сервер 'elemspec' уже зарегистрирован другой командой; "
            "проверьте его или повторите с --force"
        )
    if существующий is not None:
        удаление = subprocess.run(
            [codex, "mcp", "remove", "elemspec"], check=False
        )
        if удаление.returncode != 0:
            raise ОшибкаИнтеграции("Codex не смог удалить старый MCP elemspec")

    команда, аргументы = _команда_mcp(проект)
    добавление = subprocess.run(
        [codex, "mcp", "add", "elemspec", "--", команда, *аргументы],
        check=False,
    )
    if добавление.returncode != 0:
        raise ОшибкаИнтеграции("Codex не смог зарегистрировать MCP elemspec")


def _удалить_mcp(
    codex: str, force: bool, проект: Path | None = None
) -> None:
    существующий = _прочитать_mcp(codex)
    if существующий is None:
        return
    if not (_наш_mcp(существующий, проект) or force):
        raise ОшибкаИнтеграции(
            "MCP-сервер 'elemspec' зарегистрирован другой командой; "
            "проверьте его или повторите с --force"
        )
    удаление = subprocess.run(
        [codex, "mcp", "remove", "elemspec"], check=False
    )
    if удаление.returncode != 0:
        raise ОшибкаИнтеграции("Codex не смог удалить MCP elemspec")


def проверить_codex(проект: Path | None = None) -> dict[str, Any]:
    """Проверить глобальные skill и MCP без изменения конфигурации."""
    skill = _codex_home() / "skills" / "new-test"
    codex = _codex()
    mcp = _прочитать_mcp(codex)
    return {
        "agent": "codex",
        "skill_path": str(skill),
        "skill_installed": _наш_skill(skill),
        "mcp_installed": _наш_mcp(mcp, проект),
        "mcp_project": (
            str(проект.expanduser().resolve()) if проект is not None else None
        ),
        "ready": _наш_skill(skill) and _наш_mcp(mcp, проект),
    }


def интегрировать_codex(
    force: bool = False, проект: Path | None = None
) -> dict[str, Any]:
    """Установить пользовательский $new-test и stdio MCP ElemSpec для Codex."""
    skill = _codex_home() / "skills" / "new-test"
    codex = _codex()
    существующий_mcp = _прочитать_mcp(codex)
    if (
        (skill.exists() or skill.is_symlink())
        and not _наш_skill(skill)
        and not force
    ):
        raise ОшибкаИнтеграции(
            f"{skill} уже существует и не помечен как установка ElemSpec; "
            "проверьте его или повторите с --force"
        )
    if (
        существующий_mcp is not None
        and not _наш_mcp(существующий_mcp, проект)
        and not force
    ):
        raise ОшибкаИнтеграции(
            "MCP-сервер 'elemspec' уже зарегистрирован другой командой; "
            "проверьте его или повторите с --force"
        )
    _установить_skill(skill, force)
    _установить_mcp(codex, force, проект)
    return проверить_codex(проект)


def удалить_интеграцию_codex(
    force: bool = False, проект: Path | None = None
) -> dict[str, Any]:
    """Удалить только управляемые ElemSpec пользовательские skill и MCP."""
    skill = _codex_home() / "skills" / "new-test"
    codex = _codex()
    существующий_mcp = _прочитать_mcp(codex)
    if (
        (skill.exists() or skill.is_symlink())
        and not _наш_skill(skill)
        and not force
    ):
        raise ОшибкаИнтеграции(
            f"{skill} не помечен как установка ElemSpec; "
            "проверьте его или повторите с --force"
        )
    if (
        существующий_mcp is not None
        and not _наш_mcp(существующий_mcp, проект)
        and not force
    ):
        raise ОшибкаИнтеграции(
            "MCP-сервер 'elemspec' зарегистрирован другой командой; "
            "проверьте его или повторите с --force"
        )
    _удалить_mcp(codex, force, проект)
    _удалить_skill(skill, force)
    return {**проверить_codex(проект), "removed": True}
