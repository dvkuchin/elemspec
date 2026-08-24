from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

from elemspec import __version__


КОРЕНЬ = Path(__file__).resolve().parents[1]


class ДокументацияTest(unittest.TestCase):
    def test_канонические_документы_существуют(self) -> None:
        for имя in (
            "README.md",
            "CHANGELOG.md",
            "docs/installation.md",
            "docs/usage.md",
            "docs/language.md",
            "docs/authoring.md",
            "docs/architecture.md",
            "ROADMAP.md",
            "AGENTS.md",
            "LICENSE",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "pyproject.toml",
            "MANIFEST.in",
        ):
            self.assertTrue((КОРЕНЬ / имя).is_file(), имя)

    def test_readme_содержит_текущую_версию(self) -> None:
        readme = (КОРЕНЬ / "README.md").read_text(encoding="utf-8")
        self.assertIn(__version__, readme)

    def test_changelog_содержит_текущую_версию(self) -> None:
        changelog = (КОРЕНЬ / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(__version__, changelog)

    def test_все_зависимости_pyproject_описаны_в_установке(self) -> None:
        with (КОРЕНЬ / "pyproject.toml").open("rb") as файл:
            requirements = tomllib.load(файл)["project"]["dependencies"]
        installation = (КОРЕНЬ / "docs" / "installation.md").read_text(
            encoding="utf-8"
        )
        for requirement in requirements:
            self.assertIn(f"`{requirement}`", installation)

    def test_локальные_markdown_ссылки_не_биты(self) -> None:
        ошибки: list[str] = []
        for файл in КОРЕНЬ.rglob("*.md"):
            if any(
                часть in {".git", ".venv", ".codex-home", "_reports"}
                for часть in файл.parts
            ):
                continue
            текст = файл.read_text(encoding="utf-8")
            for ссылка in re.findall(r"\[[^\]]*\]\(([^)]+)\)", текст):
                if ссылка.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                путь = ссылка.split("#", 1)[0]
                if путь and not (файл.parent / путь).exists():
                    ошибки.append(f"{файл.relative_to(КОРЕНЬ)} -> {ссылка}")
        self.assertEqual([], ошибки)

    def test_markdown_блоки_кода_закрыты(self) -> None:
        ошибки: list[str] = []
        for файл in КОРЕНЬ.rglob("*.md"):
            if any(
                часть in {".git", ".venv", ".codex-home", "_reports"}
                for часть in файл.parts
            ):
                continue
            текст = файл.read_text(encoding="utf-8")
            if sum(строка.startswith("```") for строка in текст.splitlines()) % 2:
                ошибки.append(str(файл.relative_to(КОРЕНЬ)))
        self.assertEqual([], ошибки)

    def test_public_cli_объявлен_в_pyproject(self) -> None:
        with (КОРЕНЬ / "pyproject.toml").open("rb") as файл:
            project = tomllib.load(файл)["project"]
        scripts = project["scripts"]
        self.assertEqual("elemspec.__main__:main", scripts["elemspec"])
        self.assertEqual("MIT", project["license"])

    def test_demoCRM_входит_в_исходную_поставку(self) -> None:
        пример = КОРЕНЬ / "examples" / "demoCRM"
        for путь in (
            пример / "README.md",
            пример / "elemspec.toml",
            пример / "tests" / "democrm-smoke" / "init.json",
            пример / "tests" / "democrm-smoke" / "test.feature",
        ):
            self.assertTrue(путь.is_file(), путь)
        self.assertIn(
            "graft examples",
            (КОРЕНЬ / "MANIFEST.in").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "include CHANGELOG.md",
            (КОРЕНЬ / "MANIFEST.in").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "prune examples/demoCRM/_reports",
            (КОРЕНЬ / "MANIFEST.in").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
