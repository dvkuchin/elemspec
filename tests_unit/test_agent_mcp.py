from __future__ import annotations

import json
import tempfile
import unittest
from os import environ
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from elemspec.agent_mcp import (
    MCPRuntime,
    ВЕРСИЯ_MCP_API,
    корень_mcp,
    создать_mcp,
)


class MCPСерверTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.корень = Path(self._tmp.name)
        (self.корень / "tests").mkdir()
        (self.корень / "elemspec.toml").write_text(
            '[project]\nname = "test"\n[hosts]\nallowed = ["example.test"]\n',
            encoding="utf-8",
        )
        self.среда = MCPRuntime(self.корень)
        self.сервер = создать_mcp(self.среда)

    def tearDown(self) -> None:
        self.среда.закрыть()
        self._tmp.cleanup()

    async def test_публикует_узкие_инструменты(self) -> None:
        async with Client(self.сервер, raise_exceptions=True) as клиент:
            инструменты = (await клиент.list_tools()).tools
            имена = {инструмент.name for инструмент in инструменты}
        self.assertEqual(
            {
                "get_contract",
                "validate_test",
                "validate_draft",
                "start_session",
                "prepare_draft",
                "apply_draft",
                "prove_test",
                "register_engine_gap",
                "browser_start",
                "browser_action",
                "browser_close",
            },
            имена,
        )
        browser_action = next(
            инструмент
            for инструмент in инструменты
            if инструмент.name == "browser_action"
        )
        варианты = browser_action.input_schema["properties"]["locator_kind"][
            "anyOf"
        ][0]["enum"]
        self.assertIn("пункт навигации", варианты)
        self.assertIn("поле", варианты)

    async def test_публикует_канонический_prompt_нового_теста(self) -> None:
        async with Client(self.сервер, raise_exceptions=True) as клиент:
            prompts = await клиент.list_prompts()
            ответ = await клиент.get_prompt(
                "new_test", {"сценарий": "Проверить вход пользователя"}
            )

        self.assertEqual(["new_test"], [prompt.name for prompt in prompts.prompts])
        текст = ответ.messages[0].content.text
        self.assertIn("Проверить вход пользователя", текст)
        self.assertIn("get_contract", текст)
        self.assertIn("prove_test", текст)

    async def test_контракт_возвращает_версии_и_хосты(self) -> None:
        async with Client(self.сервер, raise_exceptions=True) as клиент:
            ответ = await клиент.call_tool("get_contract", {})
        self.assertFalse(ответ.is_error)
        self.assertEqual(ВЕРСИЯ_MCP_API, ответ.structured_content["mcp_api_version"])
        self.assertEqual(
            ["example.test"],
            ответ.structured_content["result"]["разрешённые_хосты"],
        )

    async def test_невалидное_имя_возвращает_tool_error(self) -> None:
        async with Client(self.сервер, raise_exceptions=True) as клиент:
            ответ = await клиент.call_tool(
                "start_session", {"test_name": "../outside"}
            )
        self.assertTrue(ответ.is_error)
        self.assertIn("имя каталога теста", ответ.content[0].text)

    async def test_browser_операция_требует_свои_аргументы(self) -> None:
        async with Client(self.сервер, raise_exceptions=True) as клиент:
            ответ = await клиент.call_tool(
                "browser_action",
                {
                    "browser_session": "missing",
                    "operation": "locator-check",
                },
            )
        self.assertTrue(ответ.is_error)
        self.assertIn("locator_kind и value", ответ.content[0].text)

    async def test_hover_требует_ref_из_snapshot(self) -> None:
        async with Client(self.сервер, raise_exceptions=True) as клиент:
            ответ = await клиент.call_tool(
                "browser_action",
                {
                    "browser_session": "missing",
                    "operation": "hover",
                },
            )
        self.assertTrue(ответ.is_error)
        self.assertIn("hover требует ref", ответ.content[0].text)

    async def test_read_value_требует_ref_из_snapshot(self) -> None:
        async with Client(self.сервер, raise_exceptions=True) as клиент:
            ответ = await клиент.call_tool(
                "browser_action",
                {
                    "browser_session": "missing",
                    "operation": "read-value",
                },
            )
        self.assertTrue(ответ.is_error)
        self.assertIn("read-value требует ref", ответ.content[0].text)


class ГлобальныйMCPСерверTest(unittest.IsolatedAsyncioTestCase):
    async def test_стартует_вне_проекта_и_возвращает_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            среда = MCPRuntime(Path(временный), optional_project=True)
            сервер = создать_mcp(среда)
            try:
                async with Client(сервер, raise_exceptions=True) as клиент:
                    инструменты = await клиент.list_tools()
                    ответ = await клиент.call_tool("get_contract", {})
                self.assertTrue(инструменты.tools)
                self.assertTrue(ответ.is_error)
                self.assertIn("elemspec.toml", ответ.content[0].text)
            finally:
                среда.закрыть()


class КореньMCPTest(unittest.TestCase):
    def test_приоритет_явного_проекта_над_окружением(self) -> None:
        with patch.dict(environ, {"ELEMSPEC_PROJECT": "/env/project"}, clear=True):
            self.assertEqual(Path("/explicit"), корень_mcp(Path("/explicit")))

    def test_понимает_каталог_проекта_claude(self) -> None:
        with patch.dict(
            environ, {"CLAUDE_PROJECT_DIR": "/claude/project"}, clear=True
        ):
            self.assertEqual(Path("/claude/project"), корень_mcp())


if __name__ == "__main__":
    unittest.main()
