"""JSON CLI локального ядра агентского автора тестов."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .agent import (
    ОшибкаАгентскогоAPI,
    контракт,
    проверить_тест,
    проверить_черновик,
)
from .agent_sessions import применить, подготовить, открыть_сессию
from .agent_browser import АгентскийБраузер
from .agent_evidence import открыть_разведку, записать_событие
from .agent_proof import доказать_красный
from .agent_gaps import зарегистрировать
from .project import ОшибкаПолитикиХостов, ОшибкаПроекта, ПолитикаХостов, Проект


def разобрать_аргументы(аргументы: list[str] | None = None) -> argparse.Namespace:
    парсер = argparse.ArgumentParser(
        prog="elemspec-agent",
        description="Безопасный локальный API агентского автора тестов.",
    )
    парсер.add_argument(
        "--версия",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    парсер.add_argument("--project", type=Path, default=Path.cwd())
    команды = парсер.add_subparsers(dest="команда", required=True)
    команды.add_parser("contract", help="машинный контракт языка и список тестов")
    проверка = команды.add_parser("validate", help="статически проверить тест")
    проверка.add_argument("тест", help="имя каталога непосредственно внутри tests/")
    команды.add_parser(
        "validate-draft",
        help="проверить черновик из JSON в stdin, ничего не записывая",
    )
    команды.add_parser(
        "session-start",
        help="открыть сессию; JSON в stdin: {\"имя\": \"...\"}",
    )
    команды.add_parser(
        "prepare",
        help="проверить и подготовить diff; JSON с сессией и черновиком в stdin",
    )
    команды.add_parser(
        "apply",
        help="применить подтверждённую ревизию существующего теста",
    )
    команды.add_parser(
        "browser",
        help="живая браузерная сессия; принимает и возвращает JSON Lines",
    )
    команды.add_parser(
        "prove",
        help="зелёный → временный красный → итоговый зелёный для сессии",
    )
    команды.add_parser(
        "register-gap",
        help="зарегистрировать engine-gaps/<id>.json из активной сессии",
    )
    return парсер.parse_args(аргументы)


def main(аргументы: list[str] | None = None) -> int:
    опции = разобрать_аргументы(аргументы)
    try:
        проект = Проект.найти(опции.project)
        политика = проект.политика
        тесты = проект.тесты
        сессии = проект.состояние / "sessions"
        разведки = проект.состояние / "discoveries"
        if опции.команда == "browser":
            return _цикл_браузера(политика, разведки)
        if опции.команда == "contract":
            результат = контракт(тесты, политика)
        elif опции.команда == "validate":
            результат = проверить_тест(
                тесты,
                опции.тест,
                политика,
            )
        elif опции.команда == "validate-draft":
            запрос = _прочитать_запрос(("имя", "init_json", "feature"))
            результат = проверить_черновик(
                запрос["имя"],
                запрос["init_json"],
                запрос["feature"],
                политика,
            )
        elif опции.команда == "session-start":
            запрос = _прочитать_запрос(("имя",))
            результат = открыть_сессию(
                тесты,
                сессии,
                запрос["имя"],
            )
        elif опции.команда == "prepare":
            запрос = _прочитать_запрос(
                ("сессия", "разведка", "init_json", "feature")
            )
            результат = подготовить(
                тесты,
                сессии,
                запрос["сессия"],
                запрос["init_json"],
                запрос["feature"],
                политика,
                разведки,
                запрос["разведка"],
            )
        elif опции.команда == "prove":
            запрос = _прочитать_запрос(("сессия",))
            результат = доказать_красный(
                тесты,
                сессии,
                проект.отчёты,
                запрос["сессия"],
            )
        elif опции.команда == "register-gap":
            запрос = _прочитать_запрос(("сессия", "gap"))
            результат = зарегистрировать(
                проект.корень,
                сессии,
                запрос["сессия"],
                запрос["gap"],
            )
        else:
            запрос = _прочитать_запрос(("сессия", "ревизия_черновика"))
            результат = применить(
                тесты,
                сессии,
                запрос["сессия"],
                запрос["ревизия_черновика"],
                bool(запрос.get("подтвердить_дефект", False)),
            )
    except (ОшибкаАгентскогоAPI, ОшибкаПолитикиХостов, ОшибкаПроекта) as ошибка:
        print(
            json.dumps(
                {"успех": False, "ошибка": str(ошибка)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    print(json.dumps({"успех": True, "результат": результат}, ensure_ascii=False, indent=2))
    return 0


def _прочитать_запрос(поля: tuple[str, ...]) -> dict:
    try:
        запрос = json.load(sys.stdin)
    except json.JSONDecodeError as ошибка:
        raise ОшибкаАгентскогоAPI(
            f"некорректный JSON-запрос в stdin: {ошибка.msg}, "
            f"строка {ошибка.lineno}"
        ) from ошибка
    if not isinstance(запрос, dict):
        raise ОшибкаАгентскогоAPI("JSON-запрос должен быть объектом")
    отсутствуют = [поле for поле in поля if поле not in запрос]
    if отсутствуют:
        raise ОшибкаАгентскогоAPI(
            "в JSON-запросе отсутствуют поля: " + ", ".join(отсутствуют)
        )
    return запрос


def _цикл_браузера(
    политика: ПолитикаХостов,
    каталог_разведок: Path,
) -> int:
    id_разведки = открыть_разведку(каталог_разведок)["разведка"]
    with АгентскийБраузер(политика) as браузер:
        for номер, строка in enumerate(sys.stdin, start=1):
            запрос = None
            try:
                запрос = json.loads(строка)
                if not isinstance(запрос, dict):
                    raise ОшибкаАгентскогоAPI("JSONL-запрос должен быть объектом")
                операция = запрос.get("операция")
                if операция == "start":
                    результат = браузер.открыть(запрос.get("url"))
                elif операция == "snapshot":
                    результат = браузер.снимок(запрос.get("лимит", 500))
                elif операция == "locator-check":
                    результат = браузер.проверить_локатор(
                        запрос.get("вид"),
                        запрос.get("значение"),
                    )
                elif операция == "locator-pick":
                    результат = браузер.подобрать_локатор(запрос.get("ref"))
                elif операция == "table-row-check":
                    результат = браузер.проверить_строки_таблицы(
                        запрос.get("таблица"),
                        запрос.get("колонка"),
                        запрос.get("значение"),
                    )
                elif операция == "table-row-open":
                    результат = браузер.открыть_строку_таблицы(
                        запрос.get("таблица"),
                        запрос.get("колонка"),
                        запрос.get("значение"),
                    )
                elif операция == "click":
                    результат = браузер.нажать(запрос.get("ref"))
                elif операция == "hover":
                    результат = браузер.навести(запрос.get("ref"))
                elif операция == "fill":
                    результат = браузер.ввести(
                        запрос.get("ref"),
                        запрос.get("значение"),
                    )
                elif операция == "select-value":
                    результат = браузер.выбрать_значение(
                        запрос.get("ref"),
                        запрос.get("значение"),
                    )
                elif операция == "read-value":
                    результат = браузер.прочитать_значение(запрос.get("ref"))
                elif операция == "key":
                    результат = браузер.нажать_клавишу(
                        запрос.get("клавиша")
                    )
                elif операция == "close":
                    результат = {"закрыт": True}
                    записать_событие(
                        каталог_разведок,
                        id_разведки,
                        операция,
                        запрос,
                        результат,
                    )
                    _напечатать_jsonl(запрос, результат, id_разведки)
                    return 0
                else:
                    raise ОшибкаАгентскогоAPI(
                        "операция browser должна быть: start, snapshot, "
                        "locator-check, locator-pick, table-row-check, table-row-open, "
                        "click, hover, fill, select-value, "
                        "read-value, key или close"
                    )
                записать_событие(
                    каталог_разведок,
                    id_разведки,
                    операция,
                    запрос,
                    результат,
                )
                _напечатать_jsonl(запрос, результат, id_разведки)
            except (
                json.JSONDecodeError,
                ОшибкаАгентскогоAPI,
                ОшибкаПолитикиХостов,
            ) as ошибка:
                print(
                    json.dumps(
                        {
                            "id": запрос.get("id") if isinstance(запрос, dict) else None,
                            "успех": False,
                            "ошибка": str(ошибка),
                            "строка": номер,
                            "разведка": id_разведки,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    return 0


def _напечатать_jsonl(
    запрос: dict,
    результат: dict,
    id_разведки: str,
) -> None:
    print(
        json.dumps(
            {
                "id": запрос.get("id"),
                "успех": True,
                "разведка": id_разведки,
                "результат": результат,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    sys.exit(main())
