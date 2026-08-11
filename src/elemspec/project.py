"""Настройки проекта и строгий allowlist верхнеуровневых навигаций."""

from __future__ import annotations

import ipaddress
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ОшибкаПолитикиХостов(Exception):
    """URL или конфигурация нарушают проектную политику хостов."""


class ОшибкаПроекта(Exception):
    """Не найден или некорректно настроен проект ElemSpec."""


@dataclass(frozen=True)
class Проект:
    """Независимый набор feature-тестов, использующий установленный движок."""

    корень: Path
    имя: str
    тесты: Path
    отчёты: Path
    состояние: Path
    gaps: Path
    политика: "ПолитикаХостов"

    @classmethod
    def найти(
        cls,
        указанный: Path | None = None,
        старт: Path | None = None,
    ) -> "Проект":
        if указанный is not None:
            кандидат = указанный.expanduser().resolve()
            файл = кандидат if кандидат.is_file() else кандидат / "elemspec.toml"
            if not файл.is_file():
                raise ОшибкаПроекта(f"не найден файл проекта: {файл}")
            return cls.прочитать(файл)

        текущий = (старт or Path.cwd()).expanduser().resolve()
        if текущий.is_file():
            текущий = текущий.parent
        for каталог in (текущий, *текущий.parents):
            файл = каталог / "elemspec.toml"
            if файл.is_file():
                return cls.прочитать(файл)
        raise ОшибкаПроекта(
            "не найден elemspec.toml в текущем каталоге или выше; "
            "перейдите в проект тестов или укажите --project"
        )

    @classmethod
    def прочитать(cls, файл: Path) -> "Проект":
        файл = файл.expanduser().resolve()
        try:
            данные = tomllib.loads(файл.read_text(encoding="utf-8"))
        except FileNotFoundError as ошибка:
            raise ОшибкаПроекта(f"не найден файл проекта: {файл}") from ошибка
        except tomllib.TOMLDecodeError as ошибка:
            raise ОшибкаПроекта(f"{файл}: некорректный TOML: {ошибка}") from ошибка

        проект = данные.get("project", {})
        хосты = данные.get("hosts", {})
        if not isinstance(проект, dict) or not isinstance(хосты, dict):
            raise ОшибкаПроекта("[project] и [hosts] должны быть TOML-таблицами")
        имя = проект.get("name")
        if not isinstance(имя, str) or not имя.strip():
            raise ОшибкаПроекта("[project].name должен быть непустой строкой")

        корень = файл.parent

        def путь(ключ: str, значение: str) -> Path:
            сырое = проект.get(ключ, значение)
            if not isinstance(сырое, str) or not сырое.strip():
                raise ОшибкаПроекта(f"[project].{ключ} должен быть путём")
            кандидат = Path(сырое)
            if кандидат.is_absolute():
                raise ОшибкаПроекта(f"[project].{ключ} должен быть относительным")
            итог = (корень / кандидат).resolve()
            if итог != корень and корень not in итог.parents:
                raise ОшибкаПроекта(f"[project].{ключ} выходит за корень проекта")
            return итог

        try:
            политика = ПолитикаХостов.из_списка(хосты.get("allowed"))
        except ОшибкаПолитикиХостов as ошибка:
            raise ОшибкаПроекта(f"{файл}: {ошибка}") from ошибка
        return cls(
            корень=корень,
            имя=имя.strip(),
            тесты=путь("tests_dir", "tests"),
            отчёты=путь("reports_dir", "_reports"),
            состояние=путь("state_dir", ".elemspec"),
            gaps=путь("gaps_dir", "engine-gaps"),
            политика=политика,
        )


@dataclass(frozen=True)
class ПолитикаХостов:
    разрешённые: frozenset[str]

    @classmethod
    def прочитать(cls, файл: Path) -> "ПолитикаХостов":
        try:
            данные = tomllib.loads(файл.read_text(encoding="utf-8"))
        except (FileNotFoundError, tomllib.TOMLDecodeError) as ошибка:
            raise ОшибкаПолитикиХостов(f"не удалось прочитать {файл}: {ошибка}") from ошибка
        хосты = данные.get("hosts", {})
        if not isinstance(хосты, dict):
            raise ОшибкаПолитикиХостов("[hosts] должен быть TOML-таблицей")
        return cls.из_списка(хосты.get("allowed"))

    @classmethod
    def из_списка(cls, сырые: object) -> "ПолитикаХостов":
        if not isinstance(сырые, list) or not сырые:
            raise ОшибкаПолитикиХостов(
                "[hosts].allowed должен быть непустым массивом"
            )
        нормализованные = frozenset(_нормализовать_хост(хост) for хост in сырые)
        return cls(нормализованные)

    def проверить_url(self, адрес: str) -> str:
        """Проверить абсолютный HTTP(S) URL и вернуть нормализованный hostname."""
        if not isinstance(адрес, str):
            raise ОшибкаПолитикиХостов("URL должен быть строкой")
        части = urlsplit(адрес)
        if части.scheme not in {"http", "https"} or not части.hostname:
            raise ОшибкаПолитикиХостов(
                f"разрешены только абсолютные http/https URL: {адрес!r}"
            )
        if части.username is not None or части.password is not None:
            raise ОшибкаПолитикиХостов("URL с логином или паролем запрещён")
        хост = _нормализовать_хост(части.hostname)
        if хост not in self.разрешённые:
            разрешённые = ", ".join(sorted(self.разрешённые))
            raise ОшибкаПолитикиХостов(
                f"хост '{хост}' не входит в allowlist проекта: {разрешённые}"
            )
        return хост


class ОграничительНавигации:
    """Playwright route-handler: блокирует main-frame переходы вне allowlist."""

    def __init__(self, политика: ПолитикаХостов) -> None:
        self.политика = политика
        self.заблокированный_url: str | None = None

    def __call__(self, route) -> None:
        запрос = route.request
        if запрос.is_navigation_request():
            try:
                верхний_уровень = запрос.frame.parent_frame is None
            except Exception:
                верхний_уровень = True
            if верхний_уровень:
                try:
                    self.политика.проверить_url(запрос.url)
                except ОшибкаПолитикиХостов:
                    self.заблокированный_url = запрос.url
                    route.abort("blockedbyclient")
                    return
        route.continue_()


def _нормализовать_хост(значение: object) -> str:
    if not isinstance(значение, str) or not значение.strip():
        raise ОшибкаПолитикиХостов("хост в allowlist должен быть непустой строкой")
    хост = значение.strip().rstrip(".").lower()
    if "://" in хост or "/" in хост or ":" in хост:
        # IPv6 — единственное допустимое двоеточие; urlsplit принимает его в [].
        try:
            return ipaddress.ip_address(хост.strip("[]")).compressed
        except ValueError as ошибка:
            raise ОшибкаПолитикиХостов(
                f"в allowlist нужен hostname без схемы, пути и порта: {значение!r}"
            ) from ошибка
    try:
        return ipaddress.ip_address(хост).compressed
    except ValueError:
        try:
            return хост.encode("idna").decode("ascii")
        except UnicodeError as ошибка:
            raise ОшибкаПолитикиХостов(
                f"некорректный hostname: {значение!r}"
            ) from ошибка
