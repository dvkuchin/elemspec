from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from elemspec.agent_proof import (
    СОСТОЯНИЕ_ДОКАЗАТЕЛЬСТВО_НЕВОЗМОЖНО,
    СОСТОЯНИЕ_ЗАВЕРШЕНА_С_ПРОБЕЛАМИ,
    _подтверждает_дефект,
    выбрать_мутацию,
    доказать_красный,
)
from elemspec.agent_sessions import применить, открыть_сессию, подготовить
from elemspec.agent_evidence import открыть_разведку, записать_событие


def _зелёный() -> dict:
    return {
        "тесты": [
            {
                "статус": "ок",
                "шаги": [{"статус": "ок", "снимок": None}],
            }
        ]
    }


def _красный() -> dict:
    return {
        "тесты": [
            {
                "статус": "провал",
                "шаги": [
                    {"статус": "провал", "снимок": "падение-шаг-2.png"}
                ],
            }
        ]
    }


class НегативнаяМутацияTest(unittest.TestCase):
    def test_портит_первую_позитивную_проверку(self) -> None:
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "/"\n'
            '    Тогда на странице есть текст "Готово"\n'
        )
        мутация = выбрать_мутацию(feature)
        self.assertEqual(5, мутация["строка"])
        self.assertEqual("проверить_текст", мутация["действие"])
        self.assertIn("__ELEMPWT_NEGATIVE_", мутация["feature"])

    def test_отсутствие_инвертируется_в_видимость(self) -> None:
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Тогда элемент "Ошибка" отсутствует\n'
        )
        мутация = выбрать_мутацию(feature)
        self.assertIn(
            'элемент "Ошибка" виден ровно 1 раз',
            мутация["feature"],
        )

    def test_сценарий_без_проверок_не_мутируется(self) -> None:
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "/"\n'
            '    Когда я нажимаю "Кнопка"\n'
        )
        self.assertIsNone(выбрать_мутацию(feature))

    def test_чужое_падение_не_подтверждает_заявленный_дефект(self) -> None:
        результат = {
            "тесты": [
                {
                    "статус": "провал",
                    "шаги": [
                        {
                            "имя": "Тогда другой шаг",
                            "статус": "провал",
                            "снимок": "падение.png",
                        }
                    ],
                }
            ]
        }
        сессия = {
            "подтверждённый_дефект": {
                "расхождения": [{"фраза": "Тогда ожидаемый шаг"}]
            }
        }
        self.assertFalse(_подтверждает_дефект(результат, сессия))


class ДоказательствоКрасногоTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.корень = Path(self._tmp.name)
        self.тесты = self.корень / "tests"
        self.тесты.mkdir()
        self.сессии = self.корень / "sessions"
        self.отчёты = self.корень / "reports"
        self.разведки = self.корень / "discoveries"
        (self.корень / "elemspec.toml").write_text(
            '[project]\nname = "test"\n[hosts]\nallowed = ["example.test"]\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _создать_применённую_сессию(self, feature: str) -> dict:
        сессия = открыть_сессию(self.тесты, self.сессии, "новый")
        результат = подготовить(
            self.тесты,
            self.сессии,
            сессия["сессия"],
            '{"базовый_адрес": "https://example.test"}',
            feature,
        )
        self.assertTrue(результат["применено"])
        return результат

    def test_полный_протокол_не_меняет_рабочий_feature(self) -> None:
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "/"\n'
            '    Тогда на странице есть текст "Готово"\n'
        )
        сессия = self._создать_применённую_сессию(feature)
        прогоны = []

        def runner(каталог: Path, _отчёт: Path) -> dict:
            текст = (каталог / "test.feature").read_text(encoding="utf-8")
            прогоны.append(текст)
            return _красный() if "__ELEMPWT_NEGATIVE_" in текст else _зелёный()

        результат = доказать_красный(
            self.тесты,
            self.сессии,
            self.отчёты,
            сессия["сессия"],
            runner,
        )
        self.assertEqual("COMPLETE", результат["состояние"])
        self.assertEqual(3, len(прогоны))
        self.assertEqual(feature, прогоны[0])
        self.assertIn("__ELEMPWT_NEGATIVE_", прогоны[1])
        self.assertEqual(feature, прогоны[2])
        self.assertEqual(
            feature,
            (self.тесты / "новый" / "test.feature").read_text(encoding="utf-8"),
        )

    def test_без_проверки_complete_недоступен(self) -> None:
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "/"\n'
        )
        сессия = self._создать_применённую_сессию(feature)
        результат = доказать_красный(
            self.тесты,
            self.сессии,
            self.отчёты,
            сессия["сессия"],
            lambda *_аргументы: _зелёный(),
        )
        self.assertEqual(
            СОСТОЯНИЕ_ДОКАЗАТЕЛЬСТВО_НЕВОЗМОЖНО,
            результат["состояние"],
        )

    def test_неудачную_попытку_можно_повторить_без_авторетрая(self) -> None:
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Тогда на странице есть текст "Готово"\n'
        )
        сессия = self._создать_применённую_сессию(feature)
        вызовы = 0

        def flaky_runner(каталог: Path, _отчёт: Path) -> dict:
            nonlocal вызовы
            вызовы += 1
            if вызовы == 1:
                return {"тесты": [{"статус": "сломан", "шаги": []}]}
            текст = (каталог / "test.feature").read_text(encoding="utf-8")
            return _красный() if "__ELEMPWT_NEGATIVE_" in текст else _зелёный()

        первая = доказать_красный(
            self.тесты,
            self.сессии,
            self.отчёты,
            сессия["сессия"],
            flaky_runner,
        )
        self.assertEqual("ORIGINAL_NOT_GREEN", первая["состояние"])
        self.assertEqual(1, вызовы)

        вторая = доказать_красный(
            self.тесты,
            self.сессии,
            self.отчёты,
            сессия["сессия"],
            flaky_runner,
        )
        self.assertEqual("COMPLETE", вторая["состояние"])
        self.assertEqual(4, вызовы)

    def test_подтверждённый_реальный_красный_даёт_bug_confirmed(self) -> None:
        разведка = открыть_разведку(self.разведки)["разведка"]
        записать_событие(
            self.разведки,
            разведка,
            "click",
            {"ref": "e1"},
            {
                "локатор": {"вид": "элемент", "значение": "Кнопка"},
                "новые_страницы": [],
            },
        )
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Ссылка\n'
            '    Когда клик по элемент "Кнопка" открывает вкладку с адресом '
            '"https://example.test/next"\n'
        )
        сессия = открыть_сессию(self.тесты, self.сессии, "баг")
        подготовлено = подготовить(
            self.тесты,
            self.сессии,
            сессия["сессия"],
            '{"базовый_адрес":"https://example.test"}',
            feature,
            None,
            self.разведки,
            разведка,
        )
        применить(
            self.тесты,
            self.сессии,
            сессия["сессия"],
            подготовлено["ревизия_черновика"],
            подтвердить_дефект=True,
        )

        def runner(*_аргументы) -> dict:
            return {
                "тесты": [
                    {
                        "статус": "провал",
                        "шаги": [
                            {
                                "имя": (
                                    'Когда клик по элемент "Кнопка" открывает '
                                    'вкладку с адресом "https://example.test/next"'
                                ),
                                "статус": "провал",
                                "снимок": "падение.png",
                            }
                        ],
                    }
                ]
            }

        результат = доказать_красный(
            self.тесты,
            self.сессии,
            self.отчёты,
            сессия["сессия"],
            runner,
        )
        self.assertEqual("BUG_CONFIRMED", результат["состояние"])

    def test_зарегистрированный_gap_даёт_complete_with_gaps(self) -> None:
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  # ТЗ: engine-gap:table-row-cell-value\n'
            '  Сценарий: Главная\n'
            '    Тогда на странице есть текст "Готово"\n'
        )
        сессия = self._создать_применённую_сессию(feature)
        gaps = self.корень / "engine-gaps"
        gaps.mkdir()
        (gaps / "table-row-cell-value.json").write_text(
            json.dumps(
                {
                    "версия_схемы": "1",
                    "создано_для_dsl": "0.1.0-dev.0",
                    "id": "table-row-cell-value",
                    "статус": "planned",
                    "предлагаемая_фраза": "проверить ячейку",
                    "назначение": "Проверяет значение ячейки строки",
                    "проверено_в_приложении": {
                        "поведение": "Таблица содержит строки и ячейки",
                        "локаторы": [],
                    },
                    "аргументы": [],
                    "семантика": {
                        "ок": "значение совпало",
                        "провал": "значение не совпало",
                        "сломан": "таблица не найдена",
                    },
                    "ожидание": "до таймаута теста",
                    "примеры": {
                        "позитивный": "статус совпал",
                        "негативный": "статус отличается",
                        "неоднозначный": "найдено несколько строк",
                    },
                    "критерии_готовности": ["шаг исполняется"],
                    "связанные_тесты": ["новый"],
                    "реализация": None,
                }
            ),
            encoding="utf-8",
        )

        def runner(каталог: Path, _отчёт: Path) -> dict:
            текст = (каталог / "test.feature").read_text(encoding="utf-8")
            return _красный() if "__ELEMPWT_NEGATIVE_" in текст else _зелёный()

        результат = доказать_красный(
            self.тесты,
            self.сессии,
            self.отчёты,
            сессия["сессия"],
            runner,
        )
        self.assertEqual(
            СОСТОЯНИЕ_ЗАВЕРШЕНА_С_ПРОБЕЛАМИ,
            результат["состояние"],
        )
        self.assertEqual(
            "table-row-cell-value",
            результат["gaps"]["зарегистрированные"][0]["id"],
        )

    def test_незарегистрированный_gap_не_даёт_запустить_prove(self) -> None:
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  # ТЗ: engine-gap:missing-step\n'
            '  Сценарий: Главная\n'
            '    Тогда на странице есть текст "Готово"\n'
        )
        сессия = self._создать_применённую_сессию(feature)
        вызван = False

        def runner(*_аргументы) -> dict:
            nonlocal вызван
            вызван = True
            return _зелёный()

        результат = доказать_красный(
            self.тесты,
            self.сессии,
            self.отчёты,
            сессия["сессия"],
            runner,
        )
        self.assertEqual("GAPS_NOT_REGISTERED", результат["состояние"])
        self.assertFalse(вызван)

    @unittest.skipUnless(
        os.environ.get("ELEMSPEC_LIVE_TESTS") == "1",
        "живой прогон требует Chromium и доступ к тестовому хосту",
    )
    def test_живое_доказательство_на_копии_smoke(self) -> None:
        проект = Path(__file__).resolve().parents[1]
        пример = проект / "examples" / "getting-started"
        shutil.copy2(пример / "elemspec.toml", self.корень / "elemspec.toml")
        shutil.copytree(
            пример / "tests" / "smoke",
            self.тесты / "smoke-live",
        )
        исходный = (
            self.тесты / "smoke-live" / "test.feature"
        ).read_text(encoding="utf-8")
        сессия = открыть_сессию(self.тесты, self.сессии, "smoke-live")
        подготовлено = подготовить(
            self.тесты,
            self.сессии,
            сессия["сессия"],
            (self.тесты / "smoke-live" / "init.json").read_text(encoding="utf-8"),
            исходный,
        )
        применить(
            self.тесты,
            self.сессии,
            сессия["сессия"],
            подготовлено["ревизия_черновика"],
        )
        результат = доказать_красный(
            self.тесты,
            self.сессии,
            self.отчёты,
            сессия["сессия"],
        )
        self.assertEqual("COMPLETE", результат["состояние"])
        self.assertEqual(
            исходный,
            (self.тесты / "smoke-live" / "test.feature").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
