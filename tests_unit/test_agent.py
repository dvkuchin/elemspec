from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from elemspec import __version__
from elemspec.agent import (
    ВЕРСИЯ_API,
    ВЕРСИЯ_DSL,
    ОшибкаАгентскогоAPI,
    контракт,
    проверить_тест,
    проверить_черновик,
    разрешить_тест,
)
from elemspec.agent_sessions import (
    применить,
    подготовить,
    открыть_сессию,
)
from elemspec.agent_evidence import открыть_разведку, записать_событие
from elemspec.project import ПолитикаХостов


class АгентскийAPITest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.корень = Path(self._tmp.name) / "tests"
        self.корень.mkdir()
        self.сессии = Path(self._tmp.name) / "sessions"
        self.разведки = Path(self._tmp.name) / "discoveries"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _создать_тест(self, имя: str = "пример") -> None:
        каталог = self.корень / имя
        каталог.mkdir()
        (каталог / "init.json").write_text(
            json.dumps({"базовый_адрес": "https://example.test"}),
            encoding="utf-8",
        )
        (каталог / "test.feature").write_text(
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "/"\n'
            '    Тогда на странице есть текст "Готово"\n',
            encoding="utf-8",
        )

    def test_контракт_содержит_фразы_и_тесты(self) -> None:
        self._создать_тест()
        результат = контракт(self.корень)
        self.assertEqual(ВЕРСИЯ_API, результат["версия_api"])
        self.assertEqual(ВЕРСИЯ_DSL, результат["версия_dsl"])
        self.assertEqual(__version__, результат["версия_elemspec"])
        self.assertIn("пример", результат["тесты"])
        self.assertTrue(
            any(фраза["действие"] == "открыть" for фраза in результат["фразы"])
        )

    def test_валидация_возвращает_разобранные_шаги(self) -> None:
        self._создать_тест()
        результат = проверить_тест(self.корень, "пример")
        self.assertTrue(результат["валиден"])
        действия = [
            шаг["действие"]
            for сценарий in результат["сценарии"]
            for шаг in сценарий["шаги"]
        ]
        self.assertEqual(["открыть", "проверить_текст"], действия)

    def test_путь_вместо_имени_запрещён(self) -> None:
        for имя in ("../секрет", "вложенный/тест", "/tmp/тест", ".."):
            with self.subTest(имя=имя), self.assertRaises(ОшибкаАгентскогоAPI):
                разрешить_тест(self.корень, имя)

    def test_неизвестная_фраза_делает_черновик_невалидным(self) -> None:
        self._создать_тест()
        файл = self.корень / "пример" / "test.feature"
        файл.write_text(
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Тогда всё работает правильно\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ОшибкаАгентскогоAPI, "шаг не распознан"):
            проверить_тест(self.корень, "пример")

    def test_черновик_валидируется_без_записи(self) -> None:
        результат = проверить_черновик(
            "новый-тест",
            '{"базовый_адрес": "https://example.test", '
            '"параметры": {"текст": "Готово"}}',
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "/"\n'
            '    Тогда на странице есть текст "${текст}"\n',
        )
        self.assertTrue(результат["исполняем"])
        self.assertTrue(результат["полон"])
        self.assertEqual("DRAFT_READY", результат["состояние"])
        self.assertFalse((self.корень / "новый-тест").exists())

    def test_черновик_возвращает_структурированные_ошибки(self) -> None:
        результат = проверить_черновик(
            "новый-тест",
            '{"параметры": {}}',
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Тогда неизвестное действие "${нет}"\n',
        )
        self.assertFalse(результат["исполняем"])
        self.assertEqual("INVALID", результат["состояние"])
        категории = {
            диагностика["категория"]: диагностика
            for диагностика in результат["диагностики"]
        }
        self.assertEqual(4, категории["MISSING_PARAMETER"]["строка"])
        self.assertEqual(4, категории["UNKNOWN_STEP"]["строка"])

    def test_комментарий_тз_означает_дыру_языка(self) -> None:
        результат = проверить_черновик(
            "новый-тест",
            "{}",
            '# language: ru\n'
            'Функция: Проверка\n'
            '  # ТЗ: проверить значение ячейки относительно строки\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "/"\n',
        )
        self.assertTrue(результат["исполняем"])
        self.assertFalse(результат["полон"])
        self.assertEqual("LANGUAGE_GAP", результат["состояние"])
        self.assertEqual(3, результат["пробелы_языка"][0]["строка"])
        self.assertIsNone(результат["пробелы_языка"][0]["engine_gap"])

    def test_битый_init_json_возвращает_строку(self) -> None:
        результат = проверить_черновик(
            "новый-тест",
            '{\n  "параметры":\n}',
            "",
        )
        self.assertFalse(результат["исполняем"])
        ошибка = результат["диагностики"][0]
        self.assertEqual("INIT_JSON", ошибка["категория"])
        self.assertEqual(3, ошибка["строка"])

    def test_черновик_с_чужим_хостом_невалиден(self) -> None:
        результат = проверить_черновик(
            "новый-тест",
            '{"базовый_адрес": "https://unexpected.test"}',
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "/"\n',
            ПолитикаХостов(frozenset({"allowed.test"})),
        )
        self.assertFalse(результат["исполняем"])
        self.assertEqual(
            "HOST_NOT_ALLOWED",
            результат["диагностики"][0]["категория"],
        )

    def test_новый_тест_применяется_автоматически(self) -> None:
        сессия = открыть_сессию(self.корень, self.сессии, "новый")
        результат = подготовить(
            self.корень,
            self.сессии,
            сессия["сессия"],
            "{}",
            '# language: ru\n'
            'Функция: Новый\n'
            '  Сценарий: Главная\n'
            '    Дано я открываю страницу "/"\n',
        )
        self.assertTrue(результат["применено"])
        self.assertEqual("APPLIED", результат["состояние"])
        self.assertIn("b/test.feature", результат["diff"])
        self.assertTrue((self.корень / "новый" / "init.json").is_file())

    def test_найденный_дефект_требует_явного_подтверждения(self) -> None:
        разведка = открыть_разведку(self.разведки)["разведка"]
        записать_событие(
            self.разведки,
            разведка,
            "start",
            {"url": "https://example.test"},
            {"url": "https://example.test/"},
        )
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
        сессия = открыть_сессию(self.корень, self.сессии, "баг")
        feature = (
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Ссылка\n'
            '    Когда я открываю страницу "/"\n'
            '    И клик по элемент "Кнопка" открывает вкладку с адресом '
            '"https://example.test/next"\n'
        )
        результат = подготовить(
            self.корень,
            self.сессии,
            сессия["сессия"],
            '{"базовый_адрес":"https://example.test"}',
            feature,
            None,
            self.разведки,
            разведка,
        )
        self.assertFalse(результат["применено"])
        self.assertEqual("AWAITING_BUG_CONFIRMATION", результат["состояние"])
        self.assertEqual(
            "BUG_FOUND",
            результат["browser_evidence"]["состояние"],
        )
        self.assertFalse((self.корень / "баг").exists())

        with self.assertRaisesRegex(ОшибкаАгентскогоAPI, "подтвердить_дефект"):
            применить(
                self.корень,
                self.сессии,
                сессия["сессия"],
                результат["ревизия_черновика"],
            )
        применённый = применить(
            self.корень,
            self.сессии,
            сессия["сессия"],
            результат["ревизия_черновика"],
            подтвердить_дефект=True,
        )
        self.assertTrue(применённый["применено"])
        self.assertIsNotNone(применённый["подтверждённый_дефект"])

    def test_неподтверждённый_шаг_не_применяется(self) -> None:
        разведка = открыть_разведку(self.разведки)["разведка"]
        сессия = открыть_сессию(self.корень, self.сессии, "без-доказательств")
        результат = подготовить(
            self.корень,
            self.сессии,
            сессия["сессия"],
            "{}",
            '# language: ru\n'
            'Функция: Проверка\n'
            '  Сценарий: Ссылка\n'
            '    Когда клик по элемент "Кнопка" открывает вкладку с адресом '
            '"https://example.test/next"\n',
            None,
            self.разведки,
            разведка,
        )
        self.assertEqual("UNVERIFIED", результат["состояние"])
        self.assertFalse(результат["применено"])
        self.assertFalse((self.корень / "без-доказательств").exists())

    def test_изменение_существующего_ждёт_подтверждения_ревизии(self) -> None:
        self._создать_тест()
        файл = self.корень / "пример" / "test.feature"
        исходный = файл.read_text(encoding="utf-8")
        сессия = открыть_сессию(self.корень, self.сессии, "пример")
        результат = подготовить(
            self.корень,
            self.сессии,
            сессия["сессия"],
            (self.корень / "пример" / "init.json").read_text(encoding="utf-8"),
            исходный.replace("Готово", "Выполнено"),
        )
        self.assertFalse(результат["применено"])
        self.assertEqual("AWAITING_CONFIRMATION", результат["состояние"])
        self.assertEqual(исходный, файл.read_text(encoding="utf-8"))

        применённый = применить(
            self.корень,
            self.сессии,
            сессия["сессия"],
            результат["ревизия_черновика"],
        )
        self.assertTrue(применённый["применено"])
        self.assertIn("Выполнено", файл.read_text(encoding="utf-8"))

    def test_неактуальное_подтверждение_отклоняется(self) -> None:
        self._создать_тест()
        сессия = открыть_сессию(self.корень, self.сессии, "пример")
        результат = подготовить(
            self.корень,
            self.сессии,
            сессия["сессия"],
            (self.корень / "пример" / "init.json").read_text(encoding="utf-8"),
            (self.корень / "пример" / "test.feature").read_text(encoding="utf-8"),
        )
        with self.assertRaisesRegex(ОшибкаАгентскогоAPI, "неактуальная ревизия"):
            применить(
                self.корень,
                self.сессии,
                сессия["сессия"],
                "0" * 64,
            )
        self.assertEqual("AWAITING_CONFIRMATION", результат["состояние"])

    def test_параллельное_изменение_создаёт_конфликт(self) -> None:
        self._создать_тест()
        сессия = открыть_сессию(self.корень, self.сессии, "пример")
        файл = self.корень / "пример" / "test.feature"
        файл.write_text(
            файл.read_text(encoding="utf-8") + "# внешняя правка\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ОшибкаАгентскогоAPI, "конфликт"):
            подготовить(
                self.корень,
                self.сессии,
                сессия["сессия"],
                "{}",
                '# language: ru\n'
                'Функция: Новый\n'
                '  Сценарий: Главная\n'
                '    Дано я открываю страницу "/"\n',
            )


if __name__ == "__main__":
    unittest.main()
