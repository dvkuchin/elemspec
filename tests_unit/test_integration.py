from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from elemspec.integration import (
    ОшибкаИнтеграции,
    _команда_mcp,
    _наш_skill,
    _удалить_skill,
    _установить_mcp,
    _установить_skill,
)


class CodexИнтеграцияTest(unittest.TestCase):
    def test_устанавливает_и_обновляет_собственный_skill(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            цель = Path(временный) / "skills" / "new-test"
            _установить_skill(цель, force=False)
            self.assertTrue((цель / "SKILL.md").is_file())
            self.assertTrue((цель / "references" / "api.md").is_file())
            self.assertTrue(_наш_skill(цель))

            (цель / "устаревший.txt").write_text("old", encoding="utf-8")
            _установить_skill(цель, force=False)
            self.assertFalse((цель / "устаревший.txt").exists())

    def test_не_затирает_чужой_одноимённый_skill(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            цель = Path(временный) / "new-test"
            цель.mkdir()
            (цель / "SKILL.md").write_text("чужой", encoding="utf-8")

            with self.assertRaisesRegex(ОшибкаИнтеграции, "не помечен"):
                _установить_skill(цель, force=False)
            self.assertEqual(
                "чужой", (цель / "SKILL.md").read_text(encoding="utf-8")
            )

    def test_удаляет_только_собственный_skill(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            цель = Path(временный) / "new-test"
            _установить_skill(цель, force=False)
            _удалить_skill(цель, force=False)
            self.assertFalse(цель.exists())

            цель.mkdir()
            with self.assertRaisesRegex(ОшибкаИнтеграции, "не помечен"):
                _удалить_skill(цель, force=False)

    def test_регистрирует_отсутствующий_mcp_штатной_командой_codex(self) -> None:
        команда, аргументы = _команда_mcp()
        отсутствует = CompletedProcess(
            [], 1, "", "Error: No MCP server named 'elemspec' found."
        )
        добавлен = CompletedProcess([], 0, "Added", "")
        with patch(
            "elemspec.integration.subprocess.run",
            side_effect=[отсутствует, добавлен],
        ) as run:
            _установить_mcp("/bin/codex", force=False)

        self.assertEqual(
            [
                "/bin/codex",
                "mcp",
                "add",
                "elemspec",
                "--",
                команда,
                *аргументы,
            ],
            run.call_args_list[1].args[0],
        )

    def test_команда_mcp_сохраняет_python_из_venv_даже_если_это_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            python = Path(временный) / "venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.symlink_to("/usr/bin/python3")
            with patch("elemspec.integration.sys.executable", str(python)):
                команда, _ = _команда_mcp()
            self.assertEqual(str(python), команда)

    def test_не_затирает_чужой_mcp(self) -> None:
        чужой = CompletedProcess(
            [],
            0,
            json.dumps(
                {
                    "transport": {
                        "type": "stdio",
                        "command": "other",
                        "args": [],
                    }
                }
            ),
            "",
        )
        with patch(
            "elemspec.integration.subprocess.run", return_value=чужой
        ):
            with self.assertRaisesRegex(ОшибкаИнтеграции, "другой командой"):
                _установить_mcp("/bin/codex", force=False)


if __name__ == "__main__":
    unittest.main()
