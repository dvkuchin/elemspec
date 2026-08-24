from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from playwright.sync_api import Error as ОшибкаPlaywright

from elemspec.agent_cli import _цикл_браузера


class BrowserJSONLTest(unittest.TestCase):
    def test_playwright_ошибка_операции_не_закрывает_browser_процесс(self) -> None:
        запросы = io.StringIO(
            '{"операция":"snapshot"}\n'
            '{"операция":"visible-text","лимит":100}\n'
        )
        вывод = io.StringIO()
        browser = MagicMock()
        browser.снимок.side_effect = ОшибкаPlaywright(
            "navigation interrupted snapshot"
        )
        browser.видимый_текст.return_value = {
            "текст": "Clients",
            "обрезан": False,
        }
        with tempfile.TemporaryDirectory() as временный, patch(
            "elemspec.agent_cli.АгентскийБраузер"
        ) as класс, patch("sys.stdin", запросы), redirect_stdout(вывод):
            класс.return_value.__enter__.return_value = browser
            код = _цикл_браузера(MagicMock(), Path(временный))

        ответы = [json.loads(строка) for строка in вывод.getvalue().splitlines()]
        self.assertEqual(0, код)
        self.assertFalse(ответы[0]["успех"])
        self.assertIn("navigation interrupted", ответы[0]["ошибка"])
        self.assertTrue(ответы[1]["успех"])
        self.assertEqual("Clients", ответы[1]["результат"]["текст"])


if __name__ == "__main__":
    unittest.main()
