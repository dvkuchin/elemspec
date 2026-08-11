from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from elemspec.agent_authoring import (
    _подключить_auth,
    подготовить_workspace,
    проверить_workspace,
)
from elemspec.agent_mcp import ИМЕНА_MCP_ИНСТРУМЕНТОВ


class СтрогийWorkspaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.корень = Path(self._tmp.name)
        (self.корень / "elemspec.toml").write_text(
            '[project]\nname = "test"\n[hosts]\nallowed = ["example.test"]\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_генерирует_изолированный_конфиг(self) -> None:
        результат = проверить_workspace(self.корень)
        self.assertTrue(результат["valid"], результат["errors"])
        config = Path(результат["config"]).read_text(encoding="utf-8")
        self.assertIn('sandbox_mode = "read-only"', config)
        self.assertIn('approval_policy = "never"', config)
        self.assertIn('shell_tool = false', config)
        self.assertIn('default_tools_approval_mode = "approve"', config)
        for имя in ИМЕНА_MCP_ИНСТРУМЕНТОВ:
            self.assertIn(json.dumps(имя), config)

    def test_повторная_настройка_атомарна(self) -> None:
        первый = подготовить_workspace(self.корень)
        второй = подготовить_workspace(self.корень)
        self.assertEqual(первый, второй)
        self.assertFalse(Path(второй["config"]).with_suffix(".tmp").exists())

    def test_подключает_файловую_авторизацию_ссылкой(self) -> None:
        home = self.корень / "home"
        source = home / ".codex" / "auth.json"
        source.parent.mkdir(parents=True)
        source.write_text("{}", encoding="utf-8")
        codex_home = self.корень / "isolated"
        codex_home.mkdir()
        with patch("elemspec.agent_authoring.Path.home", return_value=home):
            _подключить_auth(codex_home)
            _подключить_auth(codex_home)
        link = codex_home / "auth.json"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), source.resolve())


if __name__ == "__main__":
    unittest.main()
