"""Отдельный строгий workspace Codex для потребителя elemspec."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import NoReturn

from . import __version__
from .agent_mcp import ВЕРСИЯ_MCP_API, ИМЕНА_MCP_ИНСТРУМЕНТОВ
from .project import Проект


def подготовить_workspace(корень: Path) -> dict[str, str]:
    проект = Проект.найти(корень)
    корень = проект.корень
    workspace = проект.состояние / "authoring" / "workspace"
    codex_home = проект.состояние / "authoring" / "codex-home"
    config = codex_home / "config.toml"
    skill = Path(str(files("elemspec").joinpath("resources/skill/new-test/SKILL.md")))
    if not skill.is_file():
        raise RuntimeError(f"skill не включён в установленный пакет: {skill}")
    workspace.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    текст = _текст_конфига(корень, Path(sys.executable), skill)
    временный = config.with_suffix(".tmp")
    временный.write_text(текст, encoding="utf-8")
    os.replace(временный, config)
    return {
        "workspace": str(workspace),
        "codex_home": str(codex_home),
        "config": str(config),
        "mcp": f"{sys.executable} -m elemspec.agent_mcp --project {корень}",
        "skill": str(skill),
        "mcp_api_version": ВЕРСИЯ_MCP_API,
        "elemspec_version": __version__,
    }


def проверить_workspace(корень: Path) -> dict[str, object]:
    результат = подготовить_workspace(корень)
    config = Path(результат["config"])
    with config.open("rb") as файл:
        данные = tomllib.load(файл)
    ошибки: list[str] = []
    ожидаемые = {
        "approval_policy": "never",
        "sandbox_mode": "read-only",
        "web_search": "disabled",
        "allow_login_shell": False,
    }
    for ключ, значение in ожидаемые.items():
        if данные.get(ключ) != значение:
            ошибки.append(f"{ключ}: ожидалось {значение!r}")
    if данные.get("features") != {"shell_tool": False, "unified_exec": False}:
        ошибки.append("shell_tool и unified_exec должны быть отключены")
    if данные.get("agents") != {"enabled": False}:
        ошибки.append("subagents должны быть отключены")
    if данные.get("apps") != {"_default": {"enabled": False}}:
        ошибки.append("apps должны быть отключены")
    mcp_servers = данные.get("mcp_servers", {})
    if set(mcp_servers) != {"elemspec"}:
        ошибки.append("elemspec должен быть единственным MCP-сервером")
    сервер = mcp_servers.get("elemspec", {})
    if сервер.get("enabled_tools") != list(ИМЕНА_MCP_ИНСТРУМЕНТОВ):
        ошибки.append("набор MCP-инструментов не совпадает с контрактом")
    return {**результат, "valid": not ошибки, "errors": ошибки}


def _текст_конфига(корень: Path, python: Path, skill: Path) -> str:
    tools = ",\n  ".join(
        json.dumps(имя)
        for имя in ИМЕНА_MCP_ИНСТРУМЕНТОВ
    )
    return f'''# Сгенерирован elemspec-authoring. Не редактировать вручную.
approval_policy = "never"
sandbox_mode = "read-only"
web_search = "disabled"
allow_login_shell = false

[agents]
enabled = false

[features]
shell_tool = false
unified_exec = false

[apps._default]
enabled = false

[[skills.config]]
path = {json.dumps(str(skill))}
enabled = true

[mcp_servers.elemspec]
command = {json.dumps(str(python))}
args = ["-m", "elemspec.agent_mcp", "--project", {json.dumps(str(корень))}]
cwd = {json.dumps(str(корень))}
required = true
startup_timeout_sec = 30.0
tool_timeout_sec = 600.0
default_tools_approval_mode = "approve"
enabled_tools = [
  {tools}
]
'''


def _подключить_auth(codex_home: Path) -> None:
    """Дать изолированному CLI доступ к текущей файловой авторизации."""
    источник = Path.home() / ".codex" / "auth.json"
    ссылка = codex_home / "auth.json"
    if not источник.is_file():
        return
    if ссылка.is_symlink() and ссылка.resolve() == источник.resolve():
        return
    if ссылка.exists() or ссылка.is_symlink():
        raise RuntimeError(
            f"{ссылка} уже существует и не ссылается на текущую авторизацию"
        )
    ссылка.symlink_to(источник)


def _codex() -> str:
    найден = shutil.which("codex")
    if найден:
        return найден
    macos = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
    if macos.is_file():
        return str(macos)
    raise RuntimeError("Codex CLI не найден; установите Codex или ChatGPT desktop")


def _exec(аргументы: list[str]) -> NoReturn:
    os.execv(аргументы[0], аргументы)


def main(аргументы: list[str] | None = None) -> int:
    парсер = argparse.ArgumentParser(prog="elemspec-authoring")
    парсер.add_argument("--project", type=Path, default=Path.cwd())
    парсер.add_argument(
        "command",
        choices=("setup", "check", "cli", "exec"),
        nargs="?",
        default="setup",
    )
    парсер.add_argument("prompt", nargs="*")
    опции = парсер.parse_args(аргументы)
    корень = опции.project
    try:
        результат = (
            проверить_workspace(корень)
            if опции.command == "check"
            else подготовить_workspace(корень)
        )
        if опции.command in {"cli", "exec"}:
            _подключить_auth(Path(str(результат["codex_home"])))
            os.environ["CODEX_HOME"] = str(результат["codex_home"])
            команда = [
                _codex(),
                "-C",
                str(результат["workspace"]),
                "--strict-config",
            ]
            if опции.command == "exec":
                команда.append("exec")
            if опции.prompt:
                команда.append(" ".join(опции.prompt))
            _exec(команда)
    except (OSError, RuntimeError) as ошибка:
        print(json.dumps({"success": False, "error": str(ошибка)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "result": результат}, ensure_ascii=False, indent=2))
    return 0 if результат.get("valid", True) else 2


if __name__ == "__main__":
    sys.exit(main())
