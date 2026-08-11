"""Кроссплатформенный CLI устанавливаемого движка ElemSpec."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import webbrowser
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from . import __version__
from .engine import СТАТУС_ОК, СТАТУС_ПРОПУЩЕН, выполнить_прогон
from .model import ЗАПИСЬ_ВСЕГДА, ЗАПИСЬ_НЕТ, ЗАПИСЬ_ПРОВАЛ, найти_тесты
from .project import ОшибкаПолитикиХостов, ОшибкаПроекта, ПолитикаХостов, Проект
from .report import записать

_ЗНАЧКИ = {СТАТУС_ОК: "✓", "провал": "✗", "сломан": "!", СТАТУС_ПРОПУЩЕН: "-"}


def разобрать_аргументы(аргументы: list[str] | None = None) -> argparse.Namespace:
    парсер = argparse.ArgumentParser(
        prog="elemspec",
        description="Исполняемые UI-спецификации для приложений 1С:Элемент.",
    )
    парсер.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    парсер.add_argument(
        "--project",
        type=Path,
        help="корень проекта тестов или путь к elemspec.toml",
    )
    команды = парсер.add_subparsers(dest="команда", required=True)

    запуск = команды.add_parser("run", help="выполнить feature-тесты")
    запуск.add_argument("тесты", nargs="*", help="имена тестов; без имён — все")
    запуск.add_argument("--report", "--отчёт", dest="отчёт", type=Path)
    запуск.add_argument("--headed", "--видимый", dest="видимый", action="store_true")
    запуск.add_argument(
        "--video", "--видео", dest="запись", nargs="?", const=ЗАПИСЬ_ВСЕГДА,
        choices=sorted({ЗАПИСЬ_НЕТ, ЗАПИСЬ_ВСЕГДА, ЗАПИСЬ_ПРОВАЛ}),
    )
    запуск.add_argument("--cursor", "--курсор", dest="курсор", choices=["авто", "да", "нет"])
    запуск.add_argument("--open", "--открыть", dest="открыть", action="store_true")

    команды.add_parser("list", help="показать тесты и доступные фразы DSL")

    создание = команды.add_parser("init", help="создать новый проект feature-тестов")
    создание.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    создание.add_argument("--name", help="имя проекта")
    создание.add_argument("--host", action="append", required=True, help="разрешённый hostname")

    команды.add_parser("doctor", help="проверить проект и установленный Chromium")
    команды.add_parser("mcp", help="запустить stdio MCP для выбранного проекта")
    автор = команды.add_parser("author", help="запустить строгого ИИ-автора")
    автор.add_argument("action", choices=["setup", "check", "cli", "exec"], nargs="?", default="cli")
    автор.add_argument("prompt", nargs="*")
    браузер = команды.add_parser("install-browser", help="установить Chromium Playwright")
    браузер.add_argument("--with-deps", action="store_true", help="установить системные зависимости Linux")
    return парсер.parse_args(аргументы)


def _проект(опции: argparse.Namespace) -> Проект:
    return Проект.найти(опции.project)


def _выбрать_тесты(каталог: Path, имена: list[str]) -> list[Path]:
    доступные = найти_тесты(каталог)
    if not имена:
        return доступные
    по_имени = {путь.name: путь for путь in доступные}
    выбранные: list[Path] = []
    for имя in имена:
        путь = по_имени.get(имя.strip("/\\"))
        if путь is None:
            известные = ", ".join(sorted(по_имени)) or "нет ни одного"
            raise ОшибкаПроекта(f"тест '{имя}' не найден. Доступные: {известные}")
        выбранные.append(путь)
    return выбранные


def _инициализировать(опции: argparse.Namespace) -> int:
    корень = опции.path.expanduser().resolve()
    файл = корень / "elemspec.toml"
    if файл.exists():
        raise ОшибкаПроекта(f"проект уже существует: {файл}")
    корень.mkdir(parents=True, exist_ok=True)
    (корень / "tests").mkdir(exist_ok=True)
    gaps = корень / "engine-gaps"
    gaps.mkdir(exist_ok=True)
    имя = опции.name or корень.name
    try:
        ПолитикаХостов.из_списка(опции.host)
    except ОшибкаПолитикиХостов as ошибка:
        raise ОшибкаПроекта(str(ошибка)) from ошибка
    хосты = "\n".join(f"  {json.dumps(хост)}," for хост in опции.host)
    имя_toml = json.dumps(имя, ensure_ascii=False)
    файл.write_text(
        f'''[project]\nname = {имя_toml}\ntests_dir = "tests"\nreports_dir = "_reports"\nstate_dir = ".elemspec"\ngaps_dir = "engine-gaps"\n\n[hosts]\nallowed = [\n{хосты}\n]\n''',
        encoding="utf-8",
    )
    (gaps / "schema.json").write_text(
        files("elemspec").joinpath("resources/engine-gap.schema.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    gitignore = корень / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("_reports/\n.elemspec/\n", encoding="utf-8")
    backlog = корень / "БЭКЛОГ.md"
    if not backlog.exists():
        backlog.write_text(
            "# Бэклог тестов\n\n## Дыры языка движка\n\n"
            "Этот индекс генерируется из `engine-gaps/*.json`.\n\n"
            "<!-- engine-gaps:start -->\n_(пусто)_\n<!-- engine-gaps:end -->\n",
            encoding="utf-8",
        )
    print(f"Создан проект ElemSpec: {корень}")
    return 0


def _установить_браузер(опции: argparse.Namespace) -> int:
    команда = [sys.executable, "-m", "playwright", "install"]
    if опции.with_deps:
        команда.append("--with-deps")
    команда.append("chromium")
    return subprocess.run(команда, check=False).returncode


def _диагностика(опции: argparse.Namespace) -> int:
    проект = _проект(опции)
    тесты = найти_тесты(проект.тесты)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        chromium = Path(playwright.chromium.executable_path).is_file()
    print(f"ElemSpec: {__version__}")
    print(f"Проект:  {проект.корень}")
    print(f"Тесты:   {len(тесты)}")
    print(f"Chromium: {'установлен' if chromium else 'не найден'}")
    return 0 if chromium else 1


def _список(опции: argparse.Namespace) -> int:
    проект = _проект(опции)
    from . import steps

    print("Тесты:")
    for путь in найти_тесты(проект.тесты):
        print(f"  {путь.name}")
    print("\nФразы шагов (Gherkin):")
    print(steps.список_фраз())
    return 0


def _запустить(опции: argparse.Namespace) -> int:
    проект = _проект(опции)
    тесты = _выбрать_тесты(проект.тесты, опции.тесты)
    if not тесты:
        raise ОшибкаПроекта(f"в {проект.тесты} нет каталогов тестов с init.json")
    каталог_отчёта = опции.отчёт or (
        проект.отчёты / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    )
    if not каталог_отчёта.is_absolute():
        каталог_отчёта = проект.корень / каталог_отчёта

    print(f"Запуск тестов: {len(тесты)}")
    прогон = выполнить_прогон(
        тесты, каталог_отчёта, видимый=опции.видимый,
        запись=опции.запись, курсор_режим=опции.курсор,
    )
    файл_json, файл_html = записать(прогон, каталог_отчёта)
    print()
    for тест in прогон.тесты:
        print(f"  {_ЗНАЧКИ.get(тест.статус, '?')} {тест.имя} ({тест.длительность_с:.2f} с)")
        if тест.сообщение:
            print(f"      {тест.сообщение}")
    итоги = прогон.итоги
    print(
        f"\nИтого: {итоги['всего']} тестов, ок {итоги[СТАТУС_ОК]}, "
        f"провал {итоги['провал']}, сломан {итоги['сломан']}, "
        f"пропущен {итоги[СТАТУС_ПРОПУЩЕН]} за {прогон.длительность_с:.2f} с"
    )
    print(f"Отчёт: {файл_html}\nJSON:  {файл_json}")
    if опции.открыть and not webbrowser.open(файл_html.resolve().as_uri()):
        print("Открыть браузер не удалось — откройте отчёт вручную.", file=sys.stderr)
    return 0 if прогон.успешен else 1


def main(аргументы: list[str] | None = None) -> int:
    опции = разобрать_аргументы(аргументы)
    try:
        if опции.команда == "init":
            return _инициализировать(опции)
        if опции.команда == "install-browser":
            return _установить_браузер(опции)
        if опции.команда == "doctor":
            return _диагностика(опции)
        if опции.команда == "mcp":
            from .agent_mcp import main as mcp_main

            проект = _проект(опции)
            return mcp_main(["--project", str(проект.корень)])
        if опции.команда == "author":
            from .agent_authoring import main as author_main

            проект = _проект(опции)
            return author_main(
                ["--project", str(проект.корень), опции.action, *опции.prompt]
            )
        if опции.команда == "list":
            return _список(опции)
        return _запустить(опции)
    except ОшибкаПроекта as ошибка:
        print(f"Ошибка проекта: {ошибка}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
