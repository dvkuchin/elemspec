"""Устойчивые семантические локаторы веб-клиента 1С:Элемент."""

from __future__ import annotations

import re


КОМПОНЕНТ_ПУНКТА_НАВИГАЦИИ = "navigation-item"
КОМПОНЕНТ_МЕТКИ = "label"
СЕЛЕКТОР_ПУНКТА_НАВИГАЦИИ = (
    f'[data-component="{КОМПОНЕНТ_ПУНКТА_НАВИГАЦИИ}"]'
)
СЕЛЕКТОР_МЕТКИ = f'[data-component="{КОМПОНЕНТ_МЕТКИ}"]'


def пункт_навигации(страница, метка: str):
    """Найти ближайший navigation-item по точному тексту вложенного label."""
    точный_текст = re.compile(rf"^\s*{re.escape(метка)}\s*$")
    метки = страница.locator(СЕЛЕКТОР_МЕТКИ).filter(has_text=точный_текст)
    return метки.locator(
        f'xpath=ancestor::*[@data-component="{КОМПОНЕНТ_ПУНКТА_НАВИГАЦИИ}"][1]'
    )
