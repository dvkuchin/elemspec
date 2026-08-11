from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from elemspec.agent import ОшибкаАгентскогоAPI
from elemspec.agent_gaps import зарегистрировать
from elemspec.agent_sessions import открыть_сессию, подготовить


def _gap(id_gap: str = "table-row-cell-value") -> dict:
    return {
        "id": id_gap,
        "предлагаемая_фраза": (
            'в строке таблицы "Клиенты" где "ФИО" равно "Иванов" '
            '"Статус" содержит "Активен"'
        ),
        "назначение": "Проверять значение ячейки относительно строки таблицы",
        "проверено_в_приложении": {
            "поведение": "Строки появляются после загрузки списка",
            "локаторы": ['[data-testid="Клиенты"]', '[role="row"]'],
        },
        "аргументы": ["таблица", "колонка_поиска", "значение", "колонка_проверки"],
        "семантика": {
            "ок": "Найдена одна строка и значение соответствует",
            "провал": "Строка не найдена или значение не соответствует",
            "сломан": "Найдено несколько подходящих строк",
        },
        "ожидание": "Ждать появления единственной строки до таймаута",
        "примеры": {
            "позитивный": "Иванов имеет статус Активен",
            "негативный": "У Иванова другой статус",
            "неоднозначный": "В таблице два Иванова",
        },
        "критерии_готовности": [
            "позитивный пример зеленеет",
            "неверный статус даёт провал",
            "дубли дают сломан",
        ],
    }


class РеестрДырЯзыкаTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.корень = Path(self._tmp.name)
        self.тесты = self.корень / "tests"
        self.тесты.mkdir()
        self.сессии = self.корень / "sessions"
        (self.корень / "БЭКЛОГ.md").write_text(
            "# Бэклог\n\n## Сделано\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _сессия(self, id_gap: str = "table-row-cell-value") -> dict:
        сессия = открыть_сессию(self.тесты, self.сессии, "таблица-клиентов")
        подготовить(
            self.тесты,
            self.сессии,
            сессия["сессия"],
            "{}",
            '# language: ru\n'
            'Функция: Клиенты\n'
            f'  # ТЗ: engine-gap:{id_gap}\n'
            '  Сценарий: Статус клиента\n'
            '    Дано я открываю страницу "https://example.test"\n',
        )
        return сессия

    def test_регистрирует_json_и_обновляет_индекс(self) -> None:
        сессия = self._сессия()
        результат = зарегистрировать(
            self.корень,
            self.сессии,
            сессия["сессия"],
            _gap(),
        )
        self.assertTrue(результат["зарегистрирован"])
        файл = self.корень / "engine-gaps" / "table-row-cell-value.json"
        данные = json.loads(файл.read_text(encoding="utf-8"))
        self.assertEqual("planned", данные["статус"])
        self.assertEqual(["таблица-клиентов"], данные["связанные_тесты"])
        self.assertIsNone(данные["реализация"])
        индекс = (self.корень / "БЭКЛОГ.md").read_text(encoding="utf-8")
        self.assertIn("engine-gaps/table-row-cell-value.json", индекс)
        self.assertIn("<!-- engine-gaps:start -->", индекс)

    def test_без_ссылки_из_feature_gap_не_создаётся(self) -> None:
        сессия = открыть_сессию(self.тесты, self.сессии, "без-ссылки")
        подготовить(
            self.тесты,
            self.сессии,
            сессия["сессия"],
            "{}",
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "https://example.test"\n',
        )
        with self.assertRaisesRegex(ОшибкаАгентскогоAPI, "нет комментария"):
            зарегистрировать(
                self.корень,
                self.сессии,
                сессия["сессия"],
                _gap(),
            )

    def test_неполное_тз_отклоняется_без_файла(self) -> None:
        сессия = self._сессия()
        gap = _gap()
        del gap["семантика"]["сломан"]
        with self.assertRaisesRegex(ОшибкаАгентскогоAPI, "семантика.сломан"):
            зарегистрировать(
                self.корень,
                self.сессии,
                сессия["сессия"],
                gap,
            )
        self.assertFalse(
            (self.корень / "engine-gaps" / "table-row-cell-value.json").exists()
        )


if __name__ == "__main__":
    unittest.main()
