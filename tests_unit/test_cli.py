from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
