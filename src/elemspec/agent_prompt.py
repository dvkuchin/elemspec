"""Каноническая инструкция автора для MCP prompts и agent skills."""

from __future__ import annotations

from importlib.resources import files


def _прочитать_ресурс(имя: str) -> str:
    return (
        files("elemspec")
        .joinpath("resources/skill/new-test", имя)
        .read_text(encoding="utf-8")
    )


def _тело_skill() -> str:
    текст = _прочитать_ресурс("SKILL.md")
    if not текст.startswith("---\n"):
        raise RuntimeError("SKILL.md не содержит YAML frontmatter")
    части = текст.split("---", 2)
    if len(части) != 3:
        raise RuntimeError("SKILL.md содержит незакрытый YAML frontmatter")
    return части[2].strip()


def новый_тест_prompt(сценарий: str = "") -> str:
    """Собрать самодостаточный prompt из того же источника, что agent skill."""
    запрос = сценарий.strip() or (
        "Сначала запросить у пользователя тестируемый URL, действия и наблюдаемый "
        "ожидаемый результат. Не создавать тест без этих исходных данных."
    )
    api = _прочитать_ресурс("references/api.md").strip()
    примеры = _прочитать_ресурс("references/examples.md").strip()
    return (
        f"{_тело_skill()}\n\n"
        "## Встроенный справочник MCP API\n\n"
        f"{api}\n\n"
        "## Встроенные примеры решений\n\n"
        f"{примеры}\n\n"
        "## Сценарий пользователя\n\n"
        f"{запрос}\n"
    )
