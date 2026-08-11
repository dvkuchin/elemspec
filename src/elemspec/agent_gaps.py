"""Структурированный реестр недостающих возможностей языка elemspec."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .agent import ВЕРСИЯ_DSL, ОшибкаАгентскогоAPI
from .agent_sessions import _загрузить_сессию, _прочитать_пару


ВЕРСИЯ_СХЕМЫ_GAP = "1"
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_НАЧАЛО_ИНДЕКСА = "<!-- engine-gaps:start -->"
_КОНЕЦ_ИНДЕКСА = "<!-- engine-gaps:end -->"


def зарегистрировать(
    корень_проекта: Path,
    каталог_сессий: Path,
    id_сессии: str,
    gap: dict[str, Any],
) -> dict[str, Any]:
    """Создать новое ТЗ, связанное с feature активной рабочей сессии."""
    if not isinstance(gap, dict):
        raise ОшибкаАгентскогоAPI("'gap' должен быть JSON-объектом")
    сессия = _загрузить_сессию(каталог_сессий, id_сессии)
    id_gap = gap.get("id")
    if not isinstance(id_gap, str) or not _ID.fullmatch(id_gap):
        raise ОшибкаАгентскогоAPI(
            "gap.id должен иметь kebab-case: 'table-row-cell-value'"
        )

    feature = _feature_сессии(корень_проекта, сессия)
    ссылка = re.compile(
        rf"^\s*#\s*ТЗ:\s*engine-gap:{re.escape(id_gap)}(?:\s|$)",
        re.IGNORECASE | re.MULTILINE,
    )
    if not ссылка.search(feature):
        raise ОшибкаАгентскогоAPI(
            f"в feature нет комментария '# ТЗ: engine-gap:{id_gap}'"
        )

    документ = {
        "версия_схемы": ВЕРСИЯ_СХЕМЫ_GAP,
        "создано_для_dsl": ВЕРСИЯ_DSL,
        "id": id_gap,
        "статус": "planned",
        "предлагаемая_фраза": gap.get("предлагаемая_фраза"),
        "назначение": gap.get("назначение"),
        "проверено_в_приложении": gap.get("проверено_в_приложении"),
        "аргументы": gap.get("аргументы", []),
        "семантика": gap.get("семантика"),
        "ожидание": gap.get("ожидание"),
        "примеры": gap.get("примеры"),
        "критерии_готовности": gap.get("критерии_готовности"),
        "связанные_тесты": [сессия["тест"]],
        "реализация": None,
    }
    _валидировать(документ)

    каталог = корень_проекта / "engine-gaps"
    каталог.mkdir(parents=True, exist_ok=True)
    файл = каталог / f"{id_gap}.json"
    if файл.exists():
        raise ОшибкаАгентскогоAPI(
            f"engine gap '{id_gap}' уже существует; новый id должен быть уникальным"
        )
    _записать_json_атомарно(файл, документ)
    try:
        _обновить_индекс(корень_проекта)
    except Exception:
        файл.unlink(missing_ok=True)
        raise
    return {
        "зарегистрирован": True,
        "id": id_gap,
        "файл": str(файл),
        "статус": "planned",
        "версия_dsl_на_момент_создания": ВЕРСИЯ_DSL,
        "связанные_тесты": [сессия["тест"]],
    }


def _валидировать(документ: dict[str, Any]) -> None:
    обязательные_строки = ("предлагаемая_фраза", "назначение", "ожидание")
    for поле in обязательные_строки:
        if not isinstance(документ.get(поле), str) or not документ[поле].strip():
            raise ОшибкаАгентскогоAPI(f"gap.{поле} должен быть непустой строкой")

    наблюдение = документ.get("проверено_в_приложении")
    if not isinstance(наблюдение, dict):
        raise ОшибкаАгентскогоAPI(
            "gap.проверено_в_приложении должен быть объектом"
        )
    _непустая_строка(наблюдение, "поведение", "gap.проверено_в_приложении")
    _список_строк(наблюдение, "локаторы", "gap.проверено_в_приложении", пустой=True)

    _список_строк(документ, "аргументы", "gap", пустой=True)
    семантика = документ.get("семантика")
    if not isinstance(семантика, dict):
        raise ОшибкаАгентскогоAPI("gap.семантика должен быть объектом")
    for поле in ("ок", "провал", "сломан"):
        _непустая_строка(семантика, поле, "gap.семантика")

    примеры = документ.get("примеры")
    if not isinstance(примеры, dict):
        raise ОшибкаАгентскогоAPI("gap.примеры должен быть объектом")
    for поле in ("позитивный", "негативный", "неоднозначный"):
        _непустая_строка(примеры, поле, "gap.примеры")
    _список_строк(документ, "критерии_готовности", "gap", пустой=False)


def _непустая_строка(объект: dict, поле: str, путь: str) -> None:
    значение = объект.get(поле)
    if not isinstance(значение, str) or not значение.strip():
        raise ОшибкаАгентскогоAPI(f"{путь}.{поле} должен быть непустой строкой")


def _список_строк(
    объект: dict,
    поле: str,
    путь: str,
    *,
    пустой: bool,
) -> None:
    значение = объект.get(поле)
    if (
        not isinstance(значение, list)
        or (not пустой and not значение)
        or any(not isinstance(элемент, str) or not элемент.strip() for элемент in значение)
    ):
        требование = "массивом строк" if пустой else "непустым массивом строк"
        raise ОшибкаАгентскогоAPI(f"{путь}.{поле} должен быть {требование}")


def _feature_сессии(корень_проекта: Path, сессия: dict[str, Any]) -> str:
    черновик = сессия.get("черновик")
    if isinstance(черновик, dict) and isinstance(черновик.get("test.feature"), str):
        return черновик["test.feature"]
    тест = корень_проекта / "tests" / сессия["тест"]
    return _прочитать_пару(тест)["test.feature"]


def _обновить_индекс(корень_проекта: Path) -> None:
    записи = []
    for файл in sorted((корень_проекта / "engine-gaps").glob("*.json")):
        if файл.name == "schema.json":
            continue
        try:
            данные = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as ошибка:
            raise ОшибкаАгентскогоAPI(
                f"не удалось построить индекс: {файл}: {ошибка}"
            ) from ошибка
        записи.append(
            f"- [`{данные['id']}`](engine-gaps/{файл.name}) — "
            f"**{данные['статус']}** — {данные['назначение']}"
        )
    тело = (
        f"{_НАЧАЛО_ИНДЕКСА}\n"
        + ("\n".join(записи) if записи else "_(пусто)_")
        + f"\n{_КОНЕЦ_ИНДЕКСА}"
    )
    файл_бэклога = корень_проекта / "БЭКЛОГ.md"
    текст = файл_бэклога.read_text(encoding="utf-8")
    шаблон = re.compile(
        rf"{re.escape(_НАЧАЛО_ИНДЕКСА)}.*?{re.escape(_КОНЕЦ_ИНДЕКСА)}",
        re.DOTALL,
    )
    if шаблон.search(текст):
        новый = шаблон.sub(тело, текст)
    else:
        раздел = (
            "\n## Дыры языка движка\n\n"
            "Этот индекс генерируется из `engine-gaps/*.json`.\n\n"
            f"{тело}\n"
        )
        маркер = "\n## Сделано"
        if маркер in текст:
            новый = текст.replace(маркер, раздел + маркер, 1)
        else:
            новый = текст.rstrip() + "\n" + раздел
    _записать_текст_атомарно(файл_бэклога, новый)


def _записать_json_атомарно(файл: Path, данные: dict[str, Any]) -> None:
    _записать_текст_атомарно(
        файл,
        json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
    )


def _записать_текст_атомарно(файл: Path, текст: str) -> None:
    дескриптор, путь = tempfile.mkstemp(
        prefix=f".{файл.name}.",
        dir=файл.parent,
        text=True,
    )
    временный = Path(путь)
    try:
        with os.fdopen(дескриптор, "w", encoding="utf-8") as поток:
            поток.write(текст)
        os.replace(временный, файл)
    except OSError as ошибка:
        временный.unlink(missing_ok=True)
        raise ОшибкаАгентскогоAPI(f"не удалось записать {файл}: {ошибка}") from ошибка
