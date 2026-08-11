"""Рисованный курсор поверх страницы.

Playwright шлёт клики прямо в браузер, минуя систему, поэтому на записи не видно,
куда именно ткнули. Страница при этом получает обычные mousemove/mousedown - на них
и рисуем: точку, которая едет за мышью, и вспышку в момент клика.

Скрипт ставится через add_init_script, поэтому переживает переходы: платформа
Элемент на смене раздела перезагружает документ целиком.
"""

from __future__ import annotations

# Живёт в теневом DOM на <html>: не попадает в поиск по странице, не ловит клики
# (pointer-events: none) и не мешает тестам.
СКРИПТ = r"""
(() => {
  const МЕТКА = 'elemspec-курсор';
  const создать = () => {
    if (document.documentElement.querySelector(`[data-${МЕТКА}]`)) return;
    const хост = document.createElement('div');
    хост.setAttribute(`data-${МЕТКА}`, '');
    хост.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;' +
      'pointer-events:none;z-index:2147483647';
    const тень = хост.attachShadow({ mode: 'closed' });
    тень.innerHTML = `
      <style>
        .точка {
          position: fixed; left: 0; top: 0; width: 18px; height: 18px;
          margin: -9px 0 0 -9px; border-radius: 50%;
          background: rgba(220, 38, 38, .55);
          border: 2px solid #fff; box-shadow: 0 0 0 1px rgba(0,0,0,.4);
          opacity: 0; transition: transform .12s ease-out, opacity .2s;
          pointer-events: none;
        }
        .вспышка {
          position: fixed; left: 0; top: 0; width: 18px; height: 18px;
          margin: -9px 0 0 -9px; border-radius: 50%;
          border: 3px solid rgba(220, 38, 38, .9);
          pointer-events: none; animation: волна .5s ease-out forwards;
        }
        @keyframes волна {
          from { transform: scale(1); opacity: 1; }
          to   { transform: scale(3.5); opacity: 0; }
        }
      </style>
      <div class="точка"></div>`;
    document.documentElement.appendChild(хост);

    const точка = тень.querySelector('.точка');
    const сдвинуть = (x, y) => {
      точка.style.transform = `translate(${x}px, ${y}px)`;
      точка.style.opacity = '1';
      try { sessionStorage.setItem(МЕТКА, `${x},${y}`); } catch (е) { /* нет доступа - не беда */ }
    };

    // Платформа перезагружает документ на каждом разделе, а мышь после перехода
    // не двигается - без восстановления курсор пропал бы до конца записи.
    try {
      const было = (sessionStorage.getItem(МЕТКА) || '').split(',');
      if (было.length === 2) {
        точка.style.transition = 'none';
        сдвинуть(+было[0], +было[1]);
        requestAnimationFrame(() => { точка.style.transition = ''; });
      }
    } catch (е) { /* нет доступа - не беда */ }

    document.addEventListener('mousemove', e => сдвинуть(e.clientX, e.clientY), true);
    document.addEventListener('mousedown', e => {
      сдвинуть(e.clientX, e.clientY);
      const в = document.createElement('div');
      в.className = 'вспышка';
      в.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
      тень.appendChild(в);
      setTimeout(() => в.remove(), 600);
    }, true);
  };

  // init-скрипт выполняется раньше, чем появляется документ целиком
  if (document.documentElement) создать();
  else document.addEventListener('DOMContentLoaded', создать, { once: true });
})();
"""


def нужен(режим: str, пишем_видео: bool, видимый: bool) -> bool:
    """'авто' - рисовать только когда есть кому смотреть: запись или окно браузера."""
    if режим == "да":
        return True
    if режим == "нет":
        return False
    return пишем_видео or видимый
