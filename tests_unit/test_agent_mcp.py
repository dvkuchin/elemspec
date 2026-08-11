from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mcp import Client

from elemspec.agent_mcp import MCPRuntime, ВЕРСИЯ_MCP_API, создать_mcp


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
            имена = {инструмент.name for инструмент in (await клиент.list_tools()).tools}
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


if __name__ == "__main__":
    unittest.main()
