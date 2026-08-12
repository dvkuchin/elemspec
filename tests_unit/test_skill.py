from __future__ import annotations

import unittest
from pathlib import Path


КОРЕНЬ = Path(__file__).resolve().parents[1]
НАВЫК = КОРЕНЬ / ".agents" / "skills" / "new-test"
ПАКЕТНЫЙ_НАВЫК = КОРЕНЬ / "src" / "elemspec" / "resources" / "skill" / "new-test"


class КонтрактНавыка(unittest.TestCase):
    def test_пакетная_копия_навыка_синхронизирована(self) -> None:
        for путь in НАВЫК.rglob("*"):
            if путь.is_file():
                относительный = путь.relative_to(НАВЫК)
                self.assertEqual(
                    путь.read_bytes(),
                    (ПАКЕТНЫЙ_НАВЫК / относительный).read_bytes(),
                    str(относительный),
                )

    def test_навык_содержит_агентский_протокол(self) -> None:
        текст = (НАВЫК / "SKILL.md").read_text(encoding="utf-8")

        for требование in (
            "MCP-сервер `elemspec`",
            "get_contract",
            "browser_start",
            "browser_action",
            "пункт навигации",
            "validate_draft",
            "start_session",
            "register_engine_gap",
            "prove_test",
            "COMPLETE_WITH_GAPS",
            "BUG_CONFIRMED",
            "confirm_bug",
        ):
            self.assertIn(требование, текст)

    def test_навык_запрещает_обход_ядра(self) -> None:
        текст = (НАВЫК / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Не редактировать напрямую", текст)
        self.assertIn("Не генерировать одноразовый Playwright", текст)
        self.assertIn("Не добавлять хост", текст)
        self.assertIn("Не объявлять работу завершённой", текст)
        self.assertIn("Не использовать shell", текст)

    def test_ссылки_на_материалы_навыка_существуют(self) -> None:
        for имя in ("api.md", "examples.md"):
            self.assertTrue((НАВЫК / "references" / имя).is_file())
        self.assertTrue((НАВЫК / "agents" / "openai.yaml").is_file())
        self.assertFalse(
            (
                КОРЕНЬ
                / ".claude"
                / "skills"
                / "new-test"
                / "SKILL.md"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
