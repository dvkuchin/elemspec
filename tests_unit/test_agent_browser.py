from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from elemspec.actions import Контекст, ОшибкаДействия, получить
from elemspec.agent_browser import АгентскийБраузер, это_автоимя
from elemspec.model import Настройки
from elemspec.project import ОграничительНавигации, ПолитикаХостов


class _Фрейм:
    parent_frame = None


class _Запрос:
    def __init__(self, url: str) -> None:
        self.url = url
        self.frame = _Фрейм()

    def is_navigation_request(self) -> bool:
        return True


class _Маршрут:
    def __init__(self, url: str) -> None:
        self.request = _Запрос(url)
        self.продолжен = False
        self.прерван = False

    def continue_(self) -> None:
        self.продолжен = True

    def abort(self, _причина: str) -> None:
        self.прерван = True


class _RedirectЗапрос:
    def __init__(self, url: str, предыдущий=None) -> None:
        self.url = url
        self.redirected_from = предыдущий


class _RedirectОтвет:
    def __init__(self, запрос: _RedirectЗапрос) -> None:
        self.request = запрос


class АгентскийБраузерTest(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("ELEMPWT_BROWSER_TESTS") == "1",
        "запуск Chromium требует отдельного разрешения среды",
    )
    def test_снимок_и_проверка_локатора(self) -> None:
        политика = ПолитикаХостов(frozenset({"example.test"}))
        with АгентскийБраузер(политика) as браузер:
            браузер._страница.set_content(
                '<!doctype html><title>Тестовый стенд</title>'
                '<button data-testid="КнопкаВойти">Войти</button>'
                '<input aria-label="Имя">'
                '<div data-testid="login-edit">Login'
                '<input data-testid="base-edit-input" type="text"></div>'
                '<div data-testid="password-edit">Password'
                '<input data-testid="base-edit-input" type="password"></div>'
                '<div data-testid="ОсновнаяТаблица">'
                '<div data-component="table">'
                '<div data-component="table-row">'
                '<div data-component="table-cell">'
                '<div data-testid="Наименование">Иван</div></div>'
                '<div data-component="table-cell">'
                '<div data-testid="Регион">Москва</div></div>'
                '</div></div></div>'
                '<a href="/next">Продолжить</a>'
                '<div data-component="navigation-item" '
                'onmouseenter="this.dataset.hovered=\'yes\'" '
                'onclick="this.dataset.clicked=\'yes\'">'
                '<span data-component="label">Клиенты</span></div>'
                '<div data-component="navigation-item">'
                '<span data-component="label">Сделки</span></div>'
            )
            снимок = браузер.снимок()
            кнопка = next(
                элемент
                for элемент in снимок["элементы"]
                if элемент["testid"] == "КнопкаВойти"
            )
            поле = next(
                элемент
                for элемент in снимок["элементы"]
                if элемент["имя"] == "Имя"
            )
            поле_логина = next(
                элемент
                for элемент in снимок["элементы"]
                if элемент["тип"] == "text"
                and элемент["testid"] == "base-edit-input"
            )
            навигация = [
                элемент
                for элемент in снимок["элементы"]
                if элемент["компонент"] == "navigation-item"
            ]
            строки = [
                элемент
                for элемент in снимок["элементы"]
                if элемент["компонент"] == "table-row"
            ]
            self.assertEqual(1, len(строки))
            self.assertEqual("ОсновнаяТаблица", строки[0]["таблица"])
            проверка_строки = браузер.проверить_строки_таблицы(
                "ОсновнаяТаблица", "Наименование", "Иван"
            )
            self.assertEqual(1, проверка_строки["совпадений"])
            self.assertEqual(1, проверка_строки["видимых"])
            self.assertEqual(
                ["Клиенты", "Сделки"], [x["текст"] for x in навигация]
            )
            self.assertEqual(
                ["Клиенты", "Сделки"], [x["метка"] for x in навигация]
            )
            self.assertEqual(2, len({x["ref"] for x in навигация}))
            проверка_навигации = браузер.проверить_локатор(
                "пункт навигации", "Клиенты"
            )
            self.assertEqual(1, проверка_навигации["совпадений"])
            выбор_навигации = браузер.подобрать_локатор(навигация[0]["ref"])
            self.assertEqual(
                {"вид": "пункт навигации", "значение": "Клиенты"},
                выбор_навигации["локатор"],
            )
            self.assertFalse(выбор_навигации["долг"])
            проверка = браузер.проверить_локатор("элемент", "КнопкаВойти")
            self.assertEqual(1, проверка["совпадений"])
            self.assertEqual(1, проверка["видимых"])
            self.assertTrue(проверка["уникален"])
            выбор = браузер.подобрать_локатор(кнопка["ref"])
            self.assertEqual(
                {"вид": "элемент", "значение": "КнопкаВойти"},
                выбор["локатор"],
            )
            self.assertFalse(выбор["долг"])
            self.assertEqual(
                "login-edit", поле_логина["компонент_поля"]
            )
            проверка_поля = браузер.проверить_локатор("поле", "login-edit")
            self.assertEqual(1, проверка_поля["совпадений"])
            выбор_поля = браузер.подобрать_локатор(поле_логина["ref"])
            self.assertEqual(
                {"вид": "поле", "значение": "login-edit"},
                выбор_поля["локатор"],
            )
            self.assertFalse(выбор_поля["долг"])
            браузер.ввести(поле_логина["ref"], "TestUser")
            прочитано = браузер.прочитать_значение(поле_логина["ref"])
            self.assertEqual("TestUser", прочитано["значение"])
            self.assertEqual(
                {"вид": "поле", "значение": "login-edit"},
                прочитано["локатор"],
            )
            self.assertEqual(
                "TestUser",
                браузер._страница.locator(
                    '[data-testid="login-edit"] input'
                ).input_value(),
            )
            браузер.подобрать_локатор(поле["ref"])
            браузер.ввести(поле["ref"], "Иван")
            self.assertEqual(
                "Иван",
                браузер._страница.get_by_label("Имя").input_value(),
            )
            браузер.навести(навигация[0]["ref"])
            self.assertEqual(
                "yes",
                браузер._страница.locator(
                    "[data-component='navigation-item']"
                ).first.get_attribute("data-hovered"),
            )
            with tempfile.TemporaryDirectory() as временный:
                каталог = Path(временный)
                контекст = Контекст(
                    браузер._страница,
                    Настройки("test", каталог),
                    каталог,
                )
                получить("навести_указатель")(
                    контекст, {"пункт_навигации": "Клиенты"}
                )
                получить("ввести")(
                    контекст,
                    {
                        "поле_компонента": "password-edit",
                        "значение": "secret",
                    },
                )
                получить("проверить_значение_поля")(
                    контекст,
                    {
                        "поле_компонента": "login-edit",
                        "ожидаемое": "TestUser",
                    },
                )
                получить("очистить_поле")(
                    контекст, {"поле_компонента": "login-edit"}
                )
                получить("проверить_значение_поля")(
                    контекст,
                    {"поле_компонента": "login-edit", "ожидаемое": ""},
                )
                получить("клик")(
                    контекст, {"пункт_навигации": "Клиенты"}
                )
            self.assertEqual(
                "yes",
                браузер._страница.locator(
                    "[data-component='navigation-item']"
                ).first.get_attribute("data-clicked"),
            )

    @unittest.skipUnless(
        os.environ.get("ELEMPWT_BROWSER_TESTS") == "1",
        "запуск Chromium требует отдельного разрешения среды",
    )
    def test_вложенная_метка_адресует_ближайший_пункт(self) -> None:
        политика = ПолитикаХостов(frozenset({"example.test"}))
        with АгентскийБраузер(политика) as браузер:
            браузер._страница.set_content(
                '<div data-component="navigation-item" data-level="root">'
                '<span data-component="label">Sales</span>'
                '<div data-component="navigation-item" data-level="child">'
                '<span data-component="label">Clients</span>'
                '</div></div>'
            )
            проверка = браузер.проверить_локатор(
                "пункт навигации", "Clients"
            )
            self.assertEqual(1, проверка["совпадений"])
            self.assertEqual(["Clients"], проверка["тексты"])

    @unittest.skipUnless(
        os.environ.get("ELEMPWT_BROWSER_TESTS") == "1",
        "запуск Chromium требует отдельного разрешения среды",
    )
    def test_неоднозначная_метка_не_выбирает_первый_пункт(self) -> None:
        политика = ПолитикаХостов(frozenset({"example.test"}))
        with АгентскийБраузер(политика) as браузер:
            браузер._страница.set_content(
                '<div data-component="navigation-item">'
                '<span data-component="label">Sales</span></div>'
                '<div data-component="navigation-item">'
                '<span data-component="label">Sales</span></div>'
            )
            with tempfile.TemporaryDirectory() as временный:
                каталог = Path(временный)
                контекст = Контекст(
                    браузер._страница,
                    Настройки("test", каталог),
                    каталог,
                )
                with self.assertRaisesRegex(
                    ОшибкаДействия, "найдено элементов - 2"
                ):
                    получить("клик")(
                        контекст, {"пункт_навигации": "Sales"}
                    )

    @unittest.skipUnless(
        os.environ.get("ELEMPWT_BROWSER_TESTS") == "1",
        "запуск Chromium требует отдельного разрешения среды",
    )
    def test_компонент_с_двумя_полями_не_выбирает_первое(self) -> None:
        политика = ПолитикаХостов(frozenset({"example.test"}))
        with АгентскийБраузер(политика) as браузер:
            браузер._страница.set_content(
                '<div data-testid="period-edit">'
                '<input data-testid="base-edit-input">'
                '<input data-testid="base-edit-input">'
                '</div>'
            )
            снимок = браузер.снимок()
            первое = next(
                элемент
                for элемент in снимок["элементы"]
                if элемент["тег"] == "input"
            )
            выбор = браузер.подобрать_локатор(первое["ref"])
            self.assertTrue(выбор["долг"])
            self.assertEqual("селектор", выбор["локатор"]["вид"])
            with tempfile.TemporaryDirectory() as временный:
                каталог = Path(временный)
                контекст = Контекст(
                    браузер._страница,
                    Настройки("test", каталог),
                    каталог,
                )
                with self.assertRaisesRegex(
                    ОшибкаДействия, "найдено элементов - 2"
                ):
                    получить("ввести")(
                        контекст,
                        {"поле_компонента": "period-edit", "значение": "x"},
                    )

    def test_верхнеуровневый_переход_на_чужой_хост_блокируется(self) -> None:
        ограничитель = ОграничительНавигации(
            ПолитикаХостов(frozenset({"example.test"}))
        )
        маршрут = _Маршрут("https://unexpected.test/")
        ограничитель(маршрут)
        self.assertTrue(маршрут.прерван)
        self.assertFalse(маршрут.продолжен)
        self.assertEqual(
            "https://unexpected.test/",
            ограничитель.заблокированный_url,
        )

    def test_разрешённый_переход_продолжается(self) -> None:
        ограничитель = ОграничительНавигации(
            ПолитикаХостов(frozenset({"example.test"}))
        )
        маршрут = _Маршрут("https://example.test/path")
        ограничитель(маршрут)
        self.assertTrue(маршрут.продолжен)
        self.assertFalse(маршрут.прерван)

    def test_распознаёт_автоимена_платформы(self) -> None:
        self.assertTrue(это_автоимя("Надпись6"))
        self.assertTrue(это_автоимя("ФиксированнаяГруппа12"))
        self.assertFalse(это_автоимя("КнопкаВойти"))

    def test_сохраняет_цепочку_серверных_перенаправлений(self) -> None:
        первый = _RedirectЗапрос("https://app.example.test/demo")
        второй = _RedirectЗапрос("https://auth.example.test/signin", первый)
        self.assertEqual(
            [
                "https://app.example.test/demo",
                "https://auth.example.test/signin",
            ],
            АгентскийБраузер._цепочка_перенаправлений(
                _RedirectОтвет(второй),
                первый.url,
                второй.url,
            ),
        )


if __name__ == "__main__":
    unittest.main()
