from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
