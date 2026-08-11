from __future__ import annotations

import os
import unittest

from elemspec.agent_browser import АгентскийБраузер, это_автоимя
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
                '<a href="/next">Продолжить</a>'
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
            браузер.подобрать_локатор(поле["ref"])
            браузер.ввести(поле["ref"], "Иван")
            self.assertEqual(
                "Иван",
                браузер._страница.locator("input").input_value(),
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


if __name__ == "__main__":
    unittest.main()
