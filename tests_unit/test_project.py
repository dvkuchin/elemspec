from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from elemspec.project import ОшибкаПолитикиХостов, ПолитикаХостов, Проект


class ПолитикаХостовTest(unittest.TestCase):
    def test_находит_независимый_проект_из_дочернего_каталога(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            корень = Path(временный)
            (корень / "tests" / "smoke").mkdir(parents=True)
            (корень / "elemspec.toml").write_text(
                '[project]\nname = "demo"\n[hosts]\nallowed = ["example.test"]\n',
                encoding="utf-8",
            )
            проект = Проект.найти(старт=корень / "tests" / "smoke")
        self.assertEqual("demo", проект.имя)
        self.assertEqual(корень.resolve(), проект.корень)

    def test_читает_и_нормализует_точные_хосты(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            файл = Path(временный) / "elemspec.toml"
            файл.write_text(
                '[project]\nname = "test"\n[hosts]\n'
                'allowed = ["TEST.Example.", "127.0.0.1"]\n',
                encoding="utf-8",
            )
            политика = ПолитикаХостов.прочитать(файл)
        self.assertEqual(
            frozenset({"test.example", "127.0.0.1"}),
            политика.разрешённые,
        )
        self.assertEqual(
            "test.example",
            политика.проверить_url("https://TEST.example:8443/path"),
        )

    def test_поддомен_не_разрешается_неявно(self) -> None:
        политика = ПолитикаХостов(frozenset({"example.test"}))
        with self.assertRaisesRegex(ОшибкаПолитикиХостов, "не входит"):
            политика.проверить_url("https://api.example.test/")

    def test_запрещает_схему_путь_и_порт_в_реестре(self) -> None:
        with tempfile.TemporaryDirectory() as временный:
            файл = Path(временный) / "elemspec.toml"
            for хост in ("https://example.test", "example.test/path", "localhost:8000"):
                with self.subTest(хост=хост):
                    файл.write_text(
                        f'[project]\nname = "test"\n[hosts]\nallowed = ["{хост}"]\n',
                        encoding="utf-8",
                    )
                    with self.assertRaises(ОшибкаПолитикиХостов):
                        ПолитикаХостов.прочитать(файл)

    def test_url_с_учётными_данными_запрещён(self) -> None:
        политика = ПолитикаХостов(frozenset({"example.test"}))
        with self.assertRaisesRegex(ОшибкаПолитикиХостов, "логином"):
            политика.проверить_url("https://user:secret@example.test/")
