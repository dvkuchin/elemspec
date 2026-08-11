from __future__ import annotations

import re
import unittest

from elemspec import __version__


class ВерсияTest(unittest.TestCase):
    def test_версия_соответствует_pep440(self) -> None:
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+(?:\.dev\d+)?$")


if __name__ == "__main__":
    unittest.main()
