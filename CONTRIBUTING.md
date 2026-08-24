# Contributing to ElemSpec

Спасибо за желание улучшить ElemSpec. До первого стабильного релиза интерфейсы
могут меняться без слоя совместимости; изменение должно описывать только новый
целевой контракт.

## Подготовка

```bash
git clone https://github.com/dvkuchin/elemspec.git
cd elemspec
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e .
.venv/bin/python -m playwright install chromium
```

На Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Проверки

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests_unit -v
PYTHONPATH=src .venv/bin/python -m elemspec --project examples/getting-started run smoke
```

Unit-тесты не требуют сети. Живой smoke требует Chromium и доступ к `example.com`.
На Windows запустите те же проверки через
`.\.venv\Scripts\python.exe -m unittest discover -s tests_unit -v` и
`.\.venv\Scripts\python.exe -m elemspec --project examples/getting-started run smoke`.

## Изменения DSL

Новая фраза должна включать разбор, действие, позитивный и негативный тест,
описание неоднозначностей и обновление `docs/language.md`. Изменение конкретного проекта
feature-тестов не должно попутно менять движок.

## Документация изменения

Пользовательское изменение должно быть описано в разделе текущей версии
[`CHANGELOG.md`](CHANGELOG.md). Если меняется DSL, установка, агентский контракт
или поддерживаемый компонент Элемента, одновременно обновите соответствующий
канонический документ в `docs/`. Пакетная копия skill должна оставаться
синхронизированной с `.agents/skills/new-test/`.

Перед pull request убедитесь, что нет локальных отчётов, сессий, секретов и
абсолютных путей текущего компьютера.
