from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from elemspec.actions import (
    Контекст,
    ОшибкаДействия,
    ОшибкаПроверки,
    получить,
)
from elemspec.model import Настройки


class _Редактор:
    def __init__(self, значение: str = "") -> None:
        self.значение = значение

    def wait_for(self, **_kwargs) -> None:
        pass

    def evaluate(self, _expression: str) -> str:
        return "input"

    def input_value(self) -> str:
        return self.значение

    def get_attribute(self, _name: str):
        return None

    def fill(self, значение: str) -> None:
        self.значение = значение


class _Локатор:
    def __init__(self, редактор: _Редактор, количество: int = 1) -> None:
        self.first = редактор
        self._количество = количество

    def count(self) -> int:
        return self._количество


class _Компонент:
    def __init__(self, локатор: _Локатор) -> None:
        self._локатор = локатор

    def locator(self, _selector: str) -> _Локатор:
        return self._локатор


class _Страница:
    def __init__(self, локатор: _Локатор) -> None:
        self._компонент = _Компонент(локатор)

    def get_by_test_id(self, _name: str) -> _Компонент:
        return self._компонент

    def wait_for_timeout(self, _timeout: int) -> None:
        pass


class ЗначениеПоляTest(unittest.TestCase):
    def _контекст(self, редактор: _Редактор, количество: int = 1):
        временный = tempfile.TemporaryDirectory()
        self.addCleanup(временный.cleanup)
        каталог = Path(временный.name)
        настройки = Настройки("test", каталог, таймаут_мс=0)
        return Контекст(_Страница(_Локатор(редактор, количество)), настройки, каталог)

    def test_проверяет_точное_значение_поля(self) -> None:
        контекст = self._контекст(_Редактор("Иван"))
        результат = получить("проверить_значение_поля")(
            контекст,
            {"поле_компонента": "Имя", "ожидаемое": "Иван"},
        )
        self.assertEqual("значение поля: 'Иван'", результат)

    def test_несовпадение_значения_является_провалом_проверки(self) -> None:
        контекст = self._контекст(_Редактор("Пётр"))
        with self.assertRaisesRegex(
            ОшибкаПроверки, "значение 'Пётр', ожидалось 'Иван'"
        ):
            получить("проверить_значение_поля")(
                контекст,
                {"поле_компонента": "Имя", "ожидаемое": "Иван"},
            )

    def test_неоднозначное_поле_не_выбирает_первый_редактор(self) -> None:
        контекст = self._контекст(_Редактор("Иван"), количество=2)
        with self.assertRaisesRegex(ОшибкаДействия, "найдено элементов - 2"):
            получить("проверить_значение_поля")(
                контекст,
                {"поле_компонента": "Период", "ожидаемое": "Иван"},
            )

    def test_очищает_поле(self) -> None:
        редактор = _Редактор("Иван")
        результат = получить("очистить_поле")(
            self._контекст(редактор), {"поле_компонента": "Имя"}
        )
        self.assertEqual("", редактор.значение)
        self.assertEqual("поле очищено", результат)


class СтрокиТаблицыTest(unittest.TestCase):
    def _контекст(self, количество: int) -> Контекст:
        временный = tempfile.TemporaryDirectory()
        self.addCleanup(временный.cleanup)
        каталог = Path(временный.name)
        страница = MagicMock()
        контейнер = страница.get_by_test_id.return_value
        таблица = контейнер.locator.return_value
        строки = таблица.locator.return_value
        ячейки = таблица.get_by_test_id.return_value
        ячейки.filter.return_value = ячейки
        найденные = строки.filter.return_value
        найденные.count.return_value = количество
        найденные.first.wait_for.return_value = None
        настройки = Настройки("test", каталог, таймаут_мс=0)
        return Контекст(страница, настройки, каталог)

    def test_находит_строку_по_значению_колонки(self) -> None:
        результат = получить("проверить_строки_таблицы")(
            self._контекст(1),
            {
                "таблица": "ОсновнаяТаблица",
                "колонка": "Наименование",
                "значение_ячейки": "Иван",
            },
        )
        self.assertIn("— 1", результат)

    def test_отсутствующая_ожидаемая_строка_проваливает_проверку(self) -> None:
        with self.assertRaisesRegex(ОшибкаПроверки, "не найдена строка"):
            получить("проверить_строки_таблицы")(
                self._контекст(0),
                {
                    "таблица": "ОсновнаяТаблица",
                    "колонка": "Наименование",
                    "значение_ячейки": "Иван",
                },
            )

    def test_проверяет_отсутствие_строки(self) -> None:
        результат = получить("проверить_строки_таблицы")(
            self._контекст(0),
            {
                "таблица": "ОсновнаяТаблица",
                "колонка": "Наименование",
                "значение_ячейки": "Иван",
                "количество": 0,
            },
        )
        self.assertIn("— 0", результат)


if __name__ == "__main__":
    unittest.main()
