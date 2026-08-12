from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from elemspec.__main__ import main
from elemspec.project import Проект


class CLITest(unittest.TestCase):
    def test_init_создаёт_самодостаточный_проект(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            корень = Path(временный) / "demo-specs"
            код = main([
                "init",
                str(корень),
                "--name",
                "demo",
                "--host",
                "example.test",
            ])
            проект = Проект.найти(корень)

            self.assertEqual(0, код)
            self.assertEqual("demo", проект.имя)
            self.assertTrue((корень / "tests").is_dir())
            self.assertTrue((корень / "engine-gaps" / "schema.json").is_file())
            self.assertTrue((корень / "БЭКЛОГ.md").is_file())
            self.assertTrue((корень / ".gitignore").is_file())

    def test_init_отклоняет_url_вместо_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            код = main([
                "init",
                str(Path(временный) / "bad"),
                "--host",
                "https://example.test",
            ])
        self.assertEqual(2, код)

    def test_mcp_config_печатает_готовый_json(self) -> None:
        вывод = io.StringIO()
        with redirect_stdout(вывод):
            код = main(["mcp-config"])
        данные = json.loads(вывод.getvalue())
        self.assertEqual(0, код)
        self.assertEqual("stdio", данные["mcpServers"]["elemspec"]["type"])

    def test_integrate_codex_передаёт_явный_проект(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            проект = Path(временный)
            with patch(
                "elemspec.integration.интегрировать_codex",
                return_value={"ready": True},
            ) as интегрировать, redirect_stdout(io.StringIO()):
                код = main(
                    ["--project", str(проект), "integrate", "codex"]
                )

        self.assertEqual(0, код)
        интегрировать.assert_called_once_with(force=False, проект=проект)


if __name__ == "__main__":
    unittest.main()
