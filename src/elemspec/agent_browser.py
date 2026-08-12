"""Управляемая браузерная разведка с allowlist верхнеуровневых навигаций."""

from __future__ import annotations

import re
from typing import Any

from playwright.sync_api import Error as ОшибкаPlaywright
from playwright.sync_api import sync_playwright

from .agent import ОшибкаАгентскогоAPI
from .element_ui import (
    КОМПОНЕНТ_МЕТКИ,
    КОМПОНЕНТ_ПУНКТА_НАВИГАЦИИ,
    СЕЛЕКТОР_ПУНКТА_НАВИГАЦИИ,
    пункт_навигации,
)
from .project import ОграничительНавигации, ПолитикаХостов

_АВТОИМЯ = re.compile(
    r"^(Надпись|Группа|Картинка|ФиксированнаяГруппа|Флажок|"
    r"Кнопка|Поле|Таблица|Колонка)\d+$"
)
_СЕЛЕКТОР_АДРЕСУЕМЫХ = (
    "a, button, input, textarea, select, "
    "[role], [data-testid], [contenteditable='true'], "
    f"{СЕЛЕКТОР_ПУНКТА_НАВИГАЦИИ}"
)


def это_автоимя(имя: str | None) -> bool:
    return bool(имя and _АВТОИМЯ.fullmatch(имя))


class АгентскийБраузер:
    """Одна живая браузерная сессия для будущего MCP и локального JSONL API."""

    def __init__(
        self,
        политика: ПолитикаХостов,
        *,
        headless: bool = True,
        ширина: int = 1440,
        высота: int = 900,
    ) -> None:
        self.политика = политика
        self.headless = headless
        self.ширина = ширина
        self.высота = высота
        self._playwright = None
        self._браузер = None
        self._контекст = None
        self._страница = None
        self._ограничитель = ОграничительНавигации(политика)
        self._ссылки: dict[str, Any] = {}
        self._описания_ссылок: dict[str, dict[str, Any]] = {}
        self._выбранные_локаторы: dict[str, dict[str, str]] = {}

    def __enter__(self) -> "АгентскийБраузер":
        self._playwright = sync_playwright().start()
        self._браузер = self._playwright.chromium.launch(headless=self.headless)
        self._контекст = self._браузер.new_context(
            viewport={"width": self.ширина, "height": self.высота}
        )
        self._контекст.route("**/*", self._ограничитель)
        self._страница = self._контекст.new_page()
        self._страница.set_default_timeout(30_000)
        return self

    def __exit__(self, *_ошибка) -> None:
        if self._контекст is not None:
            self._контекст.close()
        if self._браузер is not None:
            self._браузер.close()
        if self._playwright is not None:
            self._playwright.stop()

    def открыть(self, адрес: str) -> dict[str, Any]:
        """Открыть URL и дождаться загрузки конечной страницы после redirect chain."""
        self.политика.проверить_url(адрес)
        self._ограничитель.заблокированный_url = None
        try:
            ответ = self._страница.goto(адрес, wait_until="load")
        except ОшибкаPlaywright as ошибка:
            if self._ограничитель.заблокированный_url:
                raise ОшибкаАгентскогоAPI(
                    f"навигация заблокирована allowlist: "
                    f"{self._ограничитель.заблокированный_url}"
                ) from ошибка
            raise ОшибкаАгентскогоAPI(f"не удалось открыть страницу: {ошибка}") from ошибка
        итоговый = self._страница.url
        self.политика.проверить_url(итоговый)
        цепочка = self._цепочка_перенаправлений(ответ, адрес, итоговый)
        return {
            "запрошенный_url": адрес,
            "url": итоговый,
            "перенаправлен": итоговый.rstrip("/") != адрес.rstrip("/"),
            "цепочка_url": цепочка,
            "заголовок": self._страница.title(),
            "http_статус": ответ.status if ответ else None,
        }

    @staticmethod
    def _цепочка_перенаправлений(
        ответ,
        запрошенный: str,
        итоговый: str,
    ) -> list[str]:
        запросы = []
        запрос = ответ.request if ответ is not None else None
        while запрос is not None:
            запросы.append(запрос.url)
            запрос = запрос.redirected_from
        цепочка = list(reversed(запросы))
        if not цепочка or цепочка[0] != запрошенный:
            цепочка.insert(0, запрошенный)
        if цепочка[-1] != итоговый:
            цепочка.append(итоговый)
        return цепочка

    def снимок(self, лимит: int = 500) -> dict[str, Any]:
        """Вернуть видимые адресуемые элементы без произвольного JavaScript."""
        лимит = max(1, min(int(лимит), 2_000))
        локатор = self._страница.locator(_СЕЛЕКТОР_АДРЕСУЕМЫХ)
        элементы = []
        self._ссылки = {}
        self._описания_ссылок = {}
        self._выбранные_локаторы = {}
        for индекс in range(min(локатор.count(), лимит)):
            элемент = локатор.nth(индекс)
            try:
                if not элемент.is_visible():
                    continue
                тег = элемент.evaluate("(node) => node.tagName.toLowerCase()")
                текст = элемент.inner_text().strip()
                компонент = элемент.get_attribute("data-component")
                метка = None
                if компонент == КОМПОНЕНТ_ПУНКТА_НАВИГАЦИИ:
                    метки = элемент.locator(
                        f'[data-component="{КОМПОНЕНТ_МЕТКИ}"]'
                    )
                    if метки.count():
                        метка = метки.first.inner_text().strip()
                        if метка:
                            текст = метка
                if not текст and тег in {"input", "textarea", "select"}:
                    текст = элемент.input_value()
                ref = f"e{len(элементы) + 1}"
                self._ссылки[ref] = элемент
                описание = {
                    "ref": ref,
                    "тег": тег,
                    "текст": текст[:300],
                    "роль": элемент.get_attribute("role"),
                    "testid": элемент.get_attribute("data-testid"),
                    "href": элемент.get_attribute("href"),
                    "тип": элемент.get_attribute("type"),
                    "компонент": компонент,
                    "метка": метка[:300] if метка else None,
                    "имя": (
                        элемент.get_attribute("aria-label")
                        or элемент.get_attribute("name")
                        or элемент.get_attribute("title")
                    ),
                }
                self._описания_ссылок[ref] = описание
                элементы.append(описание)
            except ОшибкаPlaywright:
                # Динамический DOM мог удалить один элемент между count и чтением.
                continue
        return {
            "url": self._страница.url,
            "заголовок": self._страница.title(),
            "элементы": элементы,
            "обрезан": локатор.count() > лимит,
        }

    def подобрать_локатор(self, ref: str) -> dict[str, Any]:
        """Пройти лестницу component → data-testid → текст → CSS."""
        элемент = self._получить_ref(ref)
        testid = элемент.get_attribute("data-testid")
        описание_ref = self._описания_ссылок.get(ref) or {}
        компонент = описание_ref.get("компонент")
        метка = описание_ref.get("метка")
        текст = str(метка or элемент.inner_text().strip())
        доказательство: dict[str, Any] = {
            "ref": ref,
            "url": self._страница.url,
            "testid": testid,
            "текст": текст[:300],
            "автоимя": это_автоимя(testid),
            "компонент": компонент,
            "метка": метка,
            "кандидаты": [],
        }

        if компонент == КОМПОНЕНТ_ПУНКТА_НАВИГАЦИИ and метка:
            проверка = self.проверить_локатор("пункт навигации", str(метка))
            доказательство["кандидаты"].append(проверка)
            if проверка["уникален"]:
                результат = {
                    "локатор": {
                        "вид": "пункт навигации",
                        "значение": str(метка),
                    },
                    "долг": False,
                    "причина": (
                        "уникальный платформенный navigation-item по точной label"
                    ),
                    "доказательство": доказательство,
                }
                self._выбранные_локаторы[ref] = результат["локатор"]
                return результат

        if testid:
            проверка = self.проверить_локатор("элемент", testid)
            доказательство["кандидаты"].append(проверка)
            if not это_автоимя(testid) and проверка["уникален"]:
                результат = {
                    "локатор": {"вид": "элемент", "значение": testid},
                    "долг": False,
                    "причина": "осмысленный уникальный data-testid",
                    "доказательство": доказательство,
                }
                self._выбранные_локаторы[ref] = результат["локатор"]
                return результат

        if текст:
            проверка = self.проверить_локатор("текст", текст)
            доказательство["кандидаты"].append(проверка)
            if проверка["уникален"]:
                результат = {
                    "локатор": {"вид": "текст", "значение": текст},
                    "долг": True,
                    "причина": (
                        "уникального осмысленного data-testid нет; "
                        "использован видимый текст"
                    ),
                    "доказательство": доказательство,
                }
                self._выбранные_локаторы[ref] = результат["локатор"]
                return результат

        css = элемент.evaluate(
            """(node) => {
                const parts = [];
                while (node && node.nodeType === 1 && node !== document.documentElement) {
                    let part = node.tagName.toLowerCase();
                    const parent = node.parentElement;
                    if (parent) {
                        const same = [...parent.children].filter(
                            item => item.tagName === node.tagName
                        );
                        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
                    }
                    parts.unshift(part);
                    node = parent;
                }
                return parts.join(' > ');
            }"""
        )
        проверка = self.проверить_локатор("селектор", css)
        доказательство["кандидаты"].append(проверка)
        результат = {
            "локатор": {"вид": "селектор", "значение": css},
            "долг": True,
            "причина": (
                "нет уникального data-testid или текста; использован хрупкий CSS"
            ),
            "доказательство": доказательство,
        }
        self._выбранные_локаторы[ref] = результат["локатор"]
        return результат

    def нажать(self, ref: str) -> dict[str, Any]:
        элемент = self._получить_ref(ref)
        локатор = self._локатор_ref(ref)
        до = self._страница.url
        страницы_до = list(self._контекст.pages)
        try:
            элемент.click()
            self._страница.wait_for_timeout(250)
        except ОшибкаPlaywright as ошибка:
            if self._ограничитель.заблокированный_url:
                raise ОшибкаАгентскогоAPI(
                    "клик попытался перейти на запрещённый хост: "
                    f"{self._ограничитель.заблокированный_url}"
                ) from ошибка
            raise ОшибкаАгентскогоAPI(f"клик не выполнен: {ошибка}") from ошибка
        страницы_после = list(self._контекст.pages)
        новые_объекты = [
            страница
            for страница in страницы_после
            if страница not in страницы_до
        ]
        for _ in range(20):
            if all(
                страница.url not in {"", "about:blank"}
                for страница in новые_объекты
            ):
                break
            self._страница.wait_for_timeout(100)
        новые = [
            страница.url
            for страница in новые_объекты
        ]
        return {
            "ref": ref,
            "локатор": локатор,
            "url_до": до,
            "url_после": self._страница.url,
            "новые_страницы": новые,
            "страниц": [страница.url for страница in страницы_после],
        }

    def навести(self, ref: str) -> dict[str, Any]:
        """Навести указатель на адресуемый элемент и дать UI обновить hover-состояние."""
        элемент = self._получить_ref(ref)
        локатор = self._локатор_ref(ref)
        try:
            элемент.hover()
            self._страница.wait_for_timeout(100)
        except ОшибкаPlaywright as ошибка:
            raise ОшибкаАгентскогоAPI(
                f"наведение указателя не выполнено: {ошибка}"
            ) from ошибка
        return {
            "ref": ref,
            "локатор": локатор,
            "url": self._страница.url,
        }

    def ввести(self, ref: str, значение: str) -> dict[str, Any]:
        if not isinstance(значение, str):
            raise ОшибкаАгентскогоAPI("значение для ввода должно быть строкой")
        элемент = self._получить_ref(ref)
        локатор = self._локатор_ref(ref)
        try:
            элемент.fill(значение)
        except ОшибкаPlaywright as ошибка:
            raise ОшибкаАгентскогоAPI(f"ввод не выполнен: {ошибка}") from ошибка
        return {
            "ref": ref,
            "локатор": локатор,
            "введено_символов": len(значение),
        }

    def нажать_клавишу(self, клавиша: str) -> dict[str, Any]:
        if not isinstance(клавиша, str) or not клавиша:
            raise ОшибкаАгентскогоAPI("имя клавиши должно быть непустой строкой")
        try:
            self._страница.keyboard.press(клавиша)
        except ОшибкаPlaywright as ошибка:
            raise ОшибкаАгентскогоAPI(
                f"клавиша не была нажата: {ошибка}"
            ) from ошибка
        return {"клавиша": клавиша}

    def проверить_локатор(self, вид: str, значение: str) -> dict[str, Any]:
        if вид == "элемент":
            локатор = self._страница.get_by_test_id(значение)
        elif вид == "пункт навигации":
            локатор = пункт_навигации(self._страница, значение)
        elif вид == "текст":
            локатор = self._страница.get_by_text(значение, exact=False)
        elif вид == "селектор":
            локатор = self._страница.locator(значение)
        else:
            raise ОшибкаАгентскогоAPI(
                "вид локатора должен быть: элемент, пункт навигации, текст или селектор"
            )
        try:
            количество = локатор.count()
            видимые = sum(
                1 for индекс in range(количество) if локатор.nth(индекс).is_visible()
            )
            тексты = []
            for индекс in range(min(количество, 10)):
                текст = локатор.nth(индекс).inner_text().strip()
                тексты.append(текст[:300])
        except ОшибкаPlaywright as ошибка:
            raise ОшибкаАгентскогоAPI(f"некорректный локатор: {ошибка}") from ошибка
        return {
            "вид": вид,
            "значение": значение,
            "совпадений": количество,
            "видимых": видимые,
            "тексты": тексты,
            "уникален": количество == 1,
        }

    def _получить_ref(self, ref: str):
        элемент = self._ссылки.get(ref)
        if элемент is None:
            raise ОшибкаАгентскогоAPI(
                f"неизвестная ссылка '{ref}'; сначала запросите новый snapshot"
            )
        return элемент

    def _локатор_ref(self, ref: str) -> dict[str, str]:
        if ref in self._выбранные_локаторы:
            return self._выбранные_локаторы[ref]
        описание = self._описания_ссылок.get(ref) or {}
        if (
            описание.get("компонент") == КОМПОНЕНТ_ПУНКТА_НАВИГАЦИИ
            and описание.get("метка")
        ):
            return {
                "вид": "пункт навигации",
                "значение": описание["метка"],
            }
        if описание.get("testid"):
            return {"вид": "элемент", "значение": описание["testid"]}
        if описание.get("текст"):
            return {"вид": "текст", "значение": описание["текст"]}
        raise ОшибкаАгентскогоAPI(
            f"для '{ref}' сначала вызовите locator-pick"
        )
