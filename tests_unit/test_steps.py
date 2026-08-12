from __future__ import annotations

import unittest

from elemspec.steps import контракт_языка, разобрать


class ПлатформенныйЛокаторTest(unittest.TestCase):
    def test_разбирает_клик_по_пункту_навигации(self) -> None:
        self.assertEqual(
            ("клик", {"пункт_навигации": "Sales"}),
            разобрать('я нажимаю пункт навигации "Sales"'),
        )

    def test_разбирает_hover_пункта_навигации(self) -> None:
        self.assertEqual(
            ("навести_указатель", {"пункт_навигации": "Sales"}),
            разобрать('я навожу указатель на пункт навигации "Sales"'),
        )

    def test_публикует_локатор_в_контракте_dsl(self) -> None:
        фразы = [запись["фраза"] for запись in контракт_языка()]
        self.assertTrue(any("пункт навигации" in фраза for фраза in фразы))


if __name__ == "__main__":
    unittest.main()
