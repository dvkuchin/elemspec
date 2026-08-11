from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from elemspec.engine import СТАТУС_СЛОМАН, выполнить_тест


class ПолитикаДвижкаTest(unittest.TestCase):
    def test_чужой_базовый_хост_ломает_тест_до_запуска_браузера(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            корень = Path(временный)
            (корень / "elemspec.toml").write_text(
                '[project]\nname = "test"\n[hosts]\nallowed = ["allowed.test"]\n',
                encoding="utf-8",
            )
            тест = корень / "tests" / "пример"
            тест.mkdir(parents=True)
            (тест / "init.json").write_text(
                json.dumps({"базовый_адрес": "https://unexpected.test"}),
                encoding="utf-8",
            )
            (тест / "test.feature").write_text(
                '# language: ru\n'
                'Функция: Проверка\n'
                '  Сценарий: Главная\n'
                '    Дано я открываю страницу "/"\n',
                encoding="utf-8",
            )
            результат = выполнить_тест(тест, корень / "reports")
        self.assertEqual(1, len(результат))
        self.assertEqual(СТАТУС_СЛОМАН, результат[0].статус)
        self.assertIn("не входит в allowlist", результат[0].сообщение)


if __name__ == "__main__":
    unittest.main()
