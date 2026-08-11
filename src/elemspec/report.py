"""Отчёты по прогону: машинный report.json и человеческий report.html."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .engine import (
    СТАТУС_ОК,
    СТАТУС_ПРОВАЛ,
    СТАТУС_ПРОПУЩЕН,
    СТАТУС_СЛОМАН,
    РезультатПрогона,
    РезультатТеста,
)

_ЦВЕТА = {
    СТАТУС_ОК: "#1f8a48",
    СТАТУС_ПРОВАЛ: "#c62828",
    СТАТУС_СЛОМАН: "#b25000",
    СТАТУС_ПРОПУЩЕН: "#6b7280",
}

_СТИЛИ = """
* { box-sizing: border-box; }
body { margin: 0; padding: 32px; background: #f4f5f7; color: #1f2328;
       font: 14px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif; }
h1 { margin: 0 0 4px; font-size: 22px; }
.мета { color: #6b7280; margin-bottom: 20px; }
.плитки { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }
.плитка { background: #fff; border: 1px solid #e3e5e8; border-radius: 10px;
          padding: 12px 20px; min-width: 110px; }
.плитка .цифра { font-size: 24px; font-weight: 600; }
.плитка .подпись { color: #6b7280; font-size: 12px; text-transform: uppercase; }
.тест { background: #fff; border: 1px solid #e3e5e8; border-radius: 10px;
        margin-bottom: 14px; overflow: hidden; }
.тест > summary { cursor: pointer; padding: 14px 18px; display: flex;
                  align-items: center; gap: 12px; list-style: none; }
.тест > summary::-webkit-details-marker { display: none; }
.тест .название { font-weight: 600; flex: 1; }
.тест .время { color: #6b7280; font-size: 12px; }
.значок { color: #fff; border-radius: 20px; padding: 2px 10px;
          font-size: 12px; font-weight: 600; }
.сообщение { padding: 0 18px 12px; color: #c62828; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 8px 18px; border-top: 1px solid #eceef0;
         vertical-align: top; }
th { background: #fafbfc; color: #6b7280; font-size: 12px; text-transform: uppercase; }
td.статус { white-space: nowrap; }
.точка { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
         margin-right: 6px; }
pre { margin: 6px 0 0; padding: 8px; background: #f6f8fa; border-radius: 6px;
      font-size: 12px; overflow-x: auto; }
img.снимок { max-width: 320px; border: 1px solid #e3e5e8; border-radius: 6px;
             margin-top: 6px; display: block; }
.запись { padding: 0 18px 14px; }
.запись video { max-width: 100%; width: 640px; border: 1px solid #e3e5e8;
                border-radius: 8px; display: block; background: #000; }
.запись .подпись { color: #6b7280; font-size: 12px; margin: 6px 0; }
@media (prefers-color-scheme: dark) {
  body { background: #16181d; color: #e6e8eb; }
  .плитка, .тест { background: #1e2127; border-color: #2f333b; }
  th { background: #22262d; }
  th, td { border-color: #2f333b; }
  pre { background: #14161a; }
}
"""


def _э(текст: object) -> str:
    return html.escape(str(текст if текст is not None else ""))


def _значок(статус: str) -> str:
    return (
        f'<span class="значок" style="background:{_ЦВЕТА.get(статус, "#6b7280")}">'
        f"{_э(статус)}</span>"
    )


def _шаги_html(тест: РезультатТеста) -> str:
    if not тест.шаги:
        return '<p class="сообщение">Шаги не выполнялись.</p>'
    строки = []
    for шаг in тест.шаги:
        цвет = _ЦВЕТА.get(шаг.статус, "#6b7280")
        подробности = (
            f"<pre>{_э(шаг.подробности)}</pre>" if шаг.подробности else ""
        )
        снимок = (
            f'<img class="снимок" src="{_э(тест.путь_артефактов)}/{_э(шаг.снимок)}" '
            f'alt="снимок падения">'
            if шаг.снимок
            else ""
        )
        строки.append(
            f"<tr>"
            f"<td>{шаг.номер}</td>"
            f'<td class="статус"><span class="точка" style="background:{цвет}"></span>'
            f"{_э(шаг.статус)}</td>"
            f"<td><b>{_э(шаг.имя)}</b><br><code>{_э(шаг.действие)}</code></td>"
            f"<td>{_э(шаг.сообщение)}{подробности}{снимок}</td>"
            f"<td>{шаг.длительность_с:.2f} с</td>"
            f"</tr>"
        )
    return (
        "<table><thead><tr><th>#</th><th>Статус</th><th>Шаг</th>"
        "<th>Результат</th><th>Время</th></tr></thead>"
        f"<tbody>{''.join(строки)}</tbody></table>"
    )


def _запись_html(тест: РезультатТеста) -> str:
    if not тест.запись:
        return ""
    путь = f"{_э(тест.путь_артефактов)}/{_э(тест.запись)}"
    return (
        f'<div class="запись"><div class="подпись">Запись прогона '
        f'(<a href="{путь}" download>скачать</a>)</div>'
        f'<video controls preload="metadata" src="{путь}"></video></div>'
    )


def _тест_html(тест: РезультатТеста) -> str:
    открыт = " open" if тест.статус != СТАТУС_ОК else ""
    описание = (
        f'<div class="мета" style="padding:0 18px 8px">{_э(тест.описание)}</div>'
        if тест.описание
        else ""
    )
    сообщение = (
        f'<div class="сообщение">{_э(тест.сообщение)}</div>' if тест.сообщение else ""
    )
    return (
        f"<details class='тест'{открыт}><summary>"
        f"{_значок(тест.статус)}"
        f'<span class="название">{_э(тест.имя)}</span>'
        f'<span class="время">{_э(тест.каталог)} · {тест.длительность_с:.2f} с</span>'
        f"</summary>{описание}{сообщение}{_запись_html(тест)}{_шаги_html(тест)}</details>"
    )


def сформировать_html(прогон: РезультатПрогона) -> str:
    итоги = прогон.итоги
    плитки = "".join(
        f'<div class="плитка"><div class="цифра" style="color:{_ЦВЕТА.get(ключ, "#1f2328")}">'
        f'{итоги.get(ключ, 0)}</div><div class="подпись">{_э(ключ)}</div></div>'
        for ключ in ("всего", СТАТУС_ОК, СТАТУС_ПРОВАЛ, СТАТУС_СЛОМАН, СТАТУС_ПРОПУЩЕН)
    )
    вердикт = _значок(СТАТУС_ОК if прогон.успешен else СТАТУС_ПРОВАЛ)
    тесты = "".join(_тест_html(тест) for тест in прогон.тесты)
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Отчёт автотестов</title>"
        f"<style>{_СТИЛИ}</style></head><body>"
        f"<h1>Отчёт автотестов {вердикт}</h1>"
        f'<div class="мета">Прогон {_э(прогон.начат)} · '
        f"{прогон.длительность_с:.2f} с</div>"
        f'<div class="плитки">{плитки}</div>{тесты}</body></html>'
    )


def записать(прогон: РезультатПрогона, каталог: Path) -> tuple[Path, Path]:
    каталог.mkdir(parents=True, exist_ok=True)
    файл_json = каталог / "report.json"
    файл_html = каталог / "report.html"
    файл_json.write_text(
        json.dumps(прогон.в_словарь(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    файл_html.write_text(сформировать_html(прогон), encoding="utf-8")
    return файл_json, файл_html
