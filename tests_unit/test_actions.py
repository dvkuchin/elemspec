from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def click(self) -> None:
        pass


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

    def test_выбирает_точное_значение_из_выпадающего_списка(self) -> None:
        редактор = _Редактор()
        списки = MagicMock()
        списки.count.return_value = 1
        вариант = MagicMock()
        вариант.click.side_effect = lambda: setattr(редактор, "значение", "Москва")
        варианты = MagicMock()
        варианты.count.return_value = 1
        варианты.first = вариант
        with (
            patch(
                "elemspec.actions.видимые_выпадающие_списки",
                return_value=списки,
            ),
            patch(
                "elemspec.actions.варианты_выпадающего_списка",
                return_value=варианты,
            ),
        ):
            результат = получить("выбрать_значение_поля")(
                self._контекст(редактор),
                {"поле_компонента": "БизнесРегион", "значение": "Москва"},
            )
        self.assertEqual("Москва", редактор.значение)
        self.assertEqual("выбрано значение: 'Москва'", результат)

    def test_сообщает_об_отсутствующем_значении_списка(self) -> None:
        списки = MagicMock()
        списки.count.return_value = 1
        варианты = MagicMock()
        варианты.count.return_value = 0
        with (
            patch(
                "elemspec.actions.видимые_выпадающие_списки",
                return_value=списки,
            ),
            patch(
                "elemspec.actions.варианты_выпадающего_списка",
                return_value=варианты,
            ),
            self.assertRaisesRegex(ОшибкаДействия, "нет значения 'Москва'"),
        ):
            получить("выбрать_значение_поля")(
                self._контекст(_Редактор()),
                {"поле_компонента": "БизнесРегион", "значение": "Москва"},
            )

    def test_не_выбирает_неоднозначное_значение_списка(self) -> None:
        списки = MagicMock()
        списки.count.return_value = 1
        варианты = MagicMock()
        варианты.count.return_value = 2
        with (
            patch(
                "elemspec.actions.видимые_выпадающие_списки",
                return_value=списки,
            ),
            patch(
                "elemspec.actions.варианты_выпадающего_списка",
                return_value=варианты,
            ),
            self.assertRaisesRegex(ОшибкаДействия, "выбор неоднозначен"),
        ):
            получить("выбрать_значение_поля")(
                self._контекст(_Редактор()),
                {"поле_компонента": "БизнесРегион", "значение": "Москва"},
            )


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
