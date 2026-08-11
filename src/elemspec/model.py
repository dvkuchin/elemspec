"""Модель данных: настройки теста (init.json) и сам тест (test.feature)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ОшибкаЗагрузки(Exception):
    """Тест не удалось прочитать - битый json/yaml, нет обязательных полей."""


_ЛОЖЬ = {"нет", "ложь", "false", "no", "off", "0", ""}


def булево(значение: Any, умолчание: bool = False) -> bool:
    """YAML не знает русских булевых: 'нет' - непустая строка, то есть Истина.
    Без этого 'не_критично: нет' означало бы ровно обратное написанному.
    """
    if значение is None:
        return умолчание
    if isinstance(значение, bool):
        return значение
    return str(значение).strip().lower() not in _ЛОЖЬ


@dataclass
class НастройкиБраузера:
    тип: str = "chromium"
    headless: bool = True
    ширина: int = 1440
    высота: int = 900
    замедление_мс: int = 0

    @classmethod
    def из_словаря(cls, данные: dict[str, Any]) -> "НастройкиБраузера":
        вьюпорт = данные.get("вьюпорт") or {}
        return cls(
            тип=данные.get("тип", "chromium"),
            headless=bool(данные.get("headless", True)),
            ширина=int(вьюпорт.get("ширина", 1440)),
            высота=int(вьюпорт.get("высота", 900)),
            замедление_мс=int(данные.get("замедление_мс", 0)),
        )


ЗАПИСЬ_НЕТ = "нет"
ЗАПИСЬ_ВСЕГДА = "всегда"
ЗАПИСЬ_ПРОВАЛ = "провал"
_РЕЖИМЫ_ЗАПИСИ = {ЗАПИСЬ_НЕТ, ЗАПИСЬ_ВСЕГДА, ЗАПИСЬ_ПРОВАЛ}

КУРСОР_АВТО = "авто"
_РЕЖИМЫ_КУРСОРА = {КУРСОР_АВТО, "да", "нет"}


@dataclass
class НастройкиЗаписи:
    """Видеозапись прогона (webm). Playwright пишет её сам, конвертация не нужна."""

    режим: str = ЗАПИСЬ_НЕТ
    ширина: int = 0  # 0 - как вьюпорт
    высота: int = 0

    @classmethod
    def из_значения(cls, значение: Any) -> "НастройкиЗаписи":
        # Допускаем и краткую форму ("запись": "всегда"), и подробную с размером.
        if значение is None:
            return cls()
        if isinstance(значение, str):
            значение = {"режим": значение}
        if not isinstance(значение, dict):
            raise ОшибкаЗагрузки(f"'запись': ожидается строка или объект, а не {значение!r}")
        режим = str(значение.get("режим", ЗАПИСЬ_НЕТ)).strip().lower()
        if режим not in _РЕЖИМЫ_ЗАПИСИ:
            допустимые = ", ".join(sorted(_РЕЖИМЫ_ЗАПИСИ))
            raise ОшибкаЗагрузки(
                f"'запись.режим': '{режим}' - неизвестный режим. Допустимые: {допустимые}"
            )
        return cls(
            режим=режим,
            ширина=int(значение.get("ширина", 0)),
            высота=int(значение.get("высота", 0)),
        )


def _разобрать_курсор(значение: Any) -> str:
    if значение is None:
        return КУРСОР_АВТО
    if isinstance(значение, bool):  # "курсор": true в json - тоже понятная запись
        return "да" if значение else "нет"
    режим = str(значение).strip().lower()
    if режим not in _РЕЖИМЫ_КУРСОРА:
        допустимые = ", ".join(sorted(_РЕЖИМЫ_КУРСОРА))
        raise ОшибкаЗагрузки(
            f"'курсор': '{режим}' - неизвестный режим. Допустимые: {допустимые}"
        )
    return режим


@dataclass
class Настройки:
    """Содержимое init.json."""

    имя: str
    каталог: Path
    базовый_адрес: str = ""
    файл_теста: str = "test.feature"
    таймаут_мс: int = 30000
    браузер: НастройкиБраузера = field(default_factory=НастройкиБраузера)
    запись: НастройкиЗаписи = field(default_factory=НастройкиЗаписи)
    курсор: str = КУРСОР_АВТО
    параметры: dict[str, Any] = field(default_factory=dict)
    пропустить: bool = False

    @classmethod
    def прочитать(cls, каталог: Path) -> "Настройки":
        файл = каталог / "init.json"
        try:
            данные = json.loads(файл.read_text(encoding="utf-8"))
        except json.JSONDecodeError as ош:
            raise ОшибкаЗагрузки(f"{файл}: некорректный JSON - {ош}") from ош
        return cls.из_словаря(данные, каталог)

    @classmethod
    def из_словаря(cls, данные: dict[str, Any], каталог: Path) -> "Настройки":
        """Разобрать уже загруженный init.json, в том числе черновик из API."""
        if not isinstance(данные, dict):
            raise ОшибкаЗагрузки("init.json: ожидается объект в корне")
        браузер = данные.get("браузер") or {}
        параметры = данные.get("параметры") or {}
        if not isinstance(браузер, dict):
            raise ОшибкаЗагрузки("init.json: 'браузер' должен быть объектом")
        if not isinstance(параметры, dict):
            raise ОшибкаЗагрузки("init.json: 'параметры' должны быть объектом")
        return cls(
            имя=данные.get("имя") or каталог.name,
            каталог=каталог,
            базовый_адрес=(данные.get("базовый_адрес") or "").rstrip("/"),
            файл_теста=данные.get("файл_теста", "test.feature"),
            таймаут_мс=int(данные.get("таймаут_мс", 30000)),
            браузер=НастройкиБраузера.из_словаря(браузер),
            запись=НастройкиЗаписи.из_значения(данные.get("запись")),
            курсор=_разобрать_курсор(данные.get("курсор")),
            параметры=параметры,
            пропустить=булево(данные.get("пропустить")),
        )


@dataclass
class Шаг:
    действие: str
    имя: str  # видимая фраза с ключевым словом: 'Когда я нажимаю "Цены"'
    аргументы: dict[str, Any]
    номер: int = 0


@dataclass
class Сценарий:
    имя: str
    шаги: list[Шаг]
    теги: list[str] = field(default_factory=list)

    @property
    def пропустить(self) -> bool:
        return "@пропустить" in self.теги


@dataclass
class Тест:
    """Содержимое test.feature: одна Функция, один и более Сценариев."""

    имя: str
    описание: str
    сценарии: list[Сценарий]
    настройки: Настройки
    теги: list[str] = field(default_factory=list)

    @classmethod
    def прочитать(cls, настройки: Настройки) -> "Тест":
        файл = настройки.каталог / настройки.файл_теста
        if not файл.exists():
            raise ОшибкаЗагрузки(f"{файл}: файл теста не найден")
        return cls.из_текста(
            настройки,
            файл.read_text(encoding="utf-8"),
            файл,
        )

    @classmethod
    def из_текста(
        cls,
        настройки: Настройки,
        текст: str,
        источник: Path | str = "test.feature",
    ) -> "Тест":
        """Разобрать Gherkin из памяти, ничего не записывая на диск."""
        from gherkin.errors import CompositeParserException
        from gherkin.parser import Parser

        источник = Path(источник)
        try:
            документ = Parser().parse(текст)
        except CompositeParserException as ош:
            raise ОшибкаЗагрузки(
                f"{источник}: некорректный Gherkin - {ош}"
            ) from ош

        функция = документ.get("feature")
        if not функция:
            raise ОшибкаЗагрузки(
                f"{источник}: нет блока 'Функция' (# language: ru?)"
            )

        предыстория: list[Шаг] = []
        сценарии: list[Сценарий] = []
        for дитя in функция["children"]:
            if "background" in дитя:
                предыстория = _шаги(дитя["background"]["steps"], источник)
            elif "scenario" in дитя:
                сценарии.extend(_сценарии(дитя["scenario"], предыстория, источник))

        if not сценарии:
            raise ОшибкаЗагрузки(
                f"{источник}: в функции нет ни одного сценария"
            )

        return cls(
            имя=функция["name"] or настройки.имя,
            описание=(функция.get("description") or "").strip(),
            сценарии=сценарии,
            настройки=настройки,
            теги=[т["name"] for т in функция.get("tags", [])],
        )


def _шаги(сырые: list[dict], файл: Path, замены: dict[str, str] | None = None) -> list[Шаг]:
    from . import steps as словарь

    шаги = []
    for сырой in сырые:
        текст = сырой["text"]
        for имя, значение in (замены or {}).items():
            текст = текст.replace(f"<{имя}>", значение)
        try:
            действие, аргументы = словарь.разобрать(текст)
        except словарь.НеизвестнаяФраза as ош:
            raise ОшибкаЗагрузки(
                f"{файл}:{сырой['location']['line']}: {ош}"
            ) from ош
        шаги.append(
            Шаг(
                действие=действие,
                имя=f"{сырой['keyword'].strip()} {текст}",
                аргументы=аргументы,
            )
        )
    return шаги


def _сценарии(сырой: dict, предыстория: list[Шаг], файл: Path) -> list[Сценарий]:
    """Обычный сценарий - один; Структура сценария разворачивается по Примерам."""
    теги = [т["name"] for т in сырой.get("tags", [])]

    def собрать(имя: str, замены: dict[str, str] | None) -> Сценарий:
        шаги = [
            Шаг(ш.действие, ш.имя, dict(ш.аргументы)) for ш in предыстория
        ] + _шаги(сырой["steps"], файл, замены)
        for номер, шаг in enumerate(шаги, start=1):
            шаг.номер = номер
        return Сценарий(имя=имя, шаги=шаги, теги=теги)

    if not сырой.get("examples"):
        return [собрать(сырой["name"], None)]

    развёрнутые = []
    for таблица in сырой["examples"]:
        заголовки = [я["value"] for я in таблица["tableHeader"]["cells"]]
        for строка in таблица["tableBody"]:
            замены = dict(zip(заголовки, [я["value"] for я in строка["cells"]]))
            подпись = ", ".join(f"{к}={з}" for к, з in замены.items())
            развёрнутые.append(собрать(f"{сырой['name']} [{подпись}]", замены))
    if not развёрнутые:
        raise ОшибкаЗагрузки(
            f"{файл}: структура сценария '{сырой['name']}' без строк в Примерах"
        )
    return развёрнутые


_ПАРАМЕТР = re.compile(r"\$\{([^}]+)\}")


def подставить(значение: Any, параметры: dict[str, Any]) -> Any:
    """Разворачивает ${имя} из 'параметры' init.json - в строках, списках, словарях."""
    if isinstance(значение, str):
        return _ПАРАМЕТР.sub(
            lambda сп: str(параметры.get(сп.group(1), сп.group(0))), значение
        )
    if isinstance(значение, list):
        return [подставить(эл, параметры) for эл in значение]
    if isinstance(значение, dict):
        return {ключ: подставить(эл, параметры) for ключ, эл in значение.items()}
    return значение


def найти_тесты(корень: Path) -> list[Path]:
    """Каталог считается тестом, если в нём лежит init.json. Служебные (_*, .*) - мимо."""
    найденные = []
    for путь in sorted(корень.iterdir()):
        if not путь.is_dir() or путь.name.startswith((".", "_")):
            continue
        if (путь / "init.json").exists():
            найденные.append(путь)
    return найденные
