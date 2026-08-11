# Установка ElemSpec

ElemSpec — устанавливаемый Python CLI. Пользователь не создаёт `.venv` вручную:
`pipx` размещает приложение и его зависимости в собственном изолированном окружении
и публикует команду `elemspec` в `PATH`.

Пока пакет не опубликован в PyPI, установка выполняется из GitHub или локального
checkout. Разработчику самого движка отдельная `.venv` по-прежнему нужна.

Установка напрямую из GitHub без клонирования репозитория:

```bash
pipx install git+https://github.com/dvkuchin/elemspec.git
elemspec install-browser
elemspec --version
```

Чтобы создавать тесты через ИИ, добавьте локальный MCP-сервер `elemspec` в интерфейсе
своего клиента. Команда печатает готовые параметры без ручного поиска Python:

```bash
elemspec mcp-config
```

Для Codex можно вместо ручного подключения одной командой установить и MCP, и
дополнительный пользовательский skill `$new-test`:

```bash
elemspec integrate codex
elemspec integrate codex --check
```

После подключения создайте новую задачу: список prompts, навыков и MCP-инструментов
формируется при её открытии. Повторный `integrate codex` безопасно обновляет установку,
которой управляет ElemSpec. Чужой одноимённый skill или MCP без явного `--force` не
перезаписывается.

## Поддерживаемые среды

- macOS — основная проверенная среда;
- Linux — поддерживается Playwright, чистый onboarding ElemSpec ещё предстоит проверить;
- Windows 11+, Windows Server 2019+ и WSL — поддерживаются Playwright; нативные
  PowerShell-команды и CI подготовлены, но ещё не подтверждены первым публичным прогоном.

Актуальные системные требования публикует
[Playwright Python](https://playwright.dev/python/docs/intro).

## Зависимости пользователя

- Python 3.11+ 64-bit;
- `pipx`;
- доступ в интернет при установке пакета и Chromium;
- Git, если установка выполняется из Git URL или checkout.

Node.js, системный Chrome, Java, Docker, Selenium/Grid, база данных и системный
ffmpeg не требуются.

Python-зависимости из [pyproject.toml](../pyproject.toml):

- `playwright==1.49.1` — браузерные действия и артефакты;
- `gherkin-official==41.0.0` — разбор Gherkin;
- `mcp==2.0.0` — stdio MCP для ИИ-автора.

## macOS

Установите системные инструменты, если их ещё нет:

```bash
brew install git python@3.11
python3 -m pip install --user --upgrade pipx
python3 -m pipx ensurepath
```

Такой способ не заставляет Homebrew собирать дополнительные версии Python и CMake
только ради `pipx`. Перезапустите терминал. Клонируйте ElemSpec и установите checkout:

```bash
git clone https://github.com/dvkuchin/elemspec.git
cd elemspec
pipx install --python python3.11 .
elemspec install-browser
elemspec --version
```

После публикации вместо checkout будет доступно:

```bash
pipx install --python python3.11 elemspec
```

## Linux

Установите Git, Python 3.11+, `python3-venv`, `pip` и `pipx` пакетным менеджером
своего дистрибутива. Затем установите checkout:

```bash
git clone https://github.com/dvkuchin/elemspec.git
cd elemspec
pipx install .
elemspec install-browser --with-deps
elemspec --version
```

`--with-deps` просит Playwright установить системные библиотеки Chromium и может
потребовать права администратора. Официальные варианты установки браузеров:
[Playwright browsers](https://playwright.dev/python/docs/browsers).

## Windows PowerShell

Установите Python 3.11+ и Git. Например, через `winget`:

```powershell
winget install Python.Python.3.11
winget install Git.Git
```

Установите `pipx`:

```powershell
py -3.11 -m pip install --user pipx
py -3.11 -m pipx ensurepath
```

Закройте и заново откройте PowerShell. Клонируйте ElemSpec и установите checkout:

```powershell
git clone https://github.com/dvkuchin/elemspec.git
Set-Location elemspec
pipx install .
elemspec install-browser
elemspec --version
```

В нативной Windows Bash-launcher не используется: `pipx` создаёт переносимую
`elemspec.exe` через стандартный Python console entry point.

## Первый проект тестов

Создайте отдельный каталог или репозиторий. В `--host` передаётся hostname без
`https://`, пути и порта:

```bash
elemspec init ./my-app-specs --name my-app --host test.example.com
cd my-app-specs
elemspec list
```

Будут созданы:

```text
my-app-specs/
├── elemspec.toml
├── tests/
├── engine-gaps/schema.json
├── БЭКЛОГ.md
└── .gitignore
```

Запуск:

```bash
elemspec run
elemspec run smoke
elemspec --project /path/to/my-app-specs run
```

## Проверка checkout движка

В репозитории ElemSpec есть независимый пример:

```bash
elemspec --project examples/getting-started list
elemspec --project examples/getting-started run smoke
```

Ожидается один зелёный сценарий и код возврата `0`. Нужен доступ к
`https://example.com`.

## ИИ-автор тестов

Для выполнения готовых feature-тестов ИИ не нужен. Для их создания подойдёт локальный
ИИ-клиент с поддержкой stdio MCP. Выполните:

```bash
elemspec mcp-config
```

В интерфейсе клиента выберите добавление MCP-сервера и перенесите `command` и `args`
из JSON. Если клиент запускает сервер не из рабочего каталога проекта, сформируйте
привязанную конфигурацию:

```bash
elemspec --project /absolute/path/to/my-specs mcp-config
```

После подключения используйте MCP prompt `new_test`, если клиент показывает prompts.
В Claude Code он имеет имя `/mcp__elemspec__new_test`. Если prompts не отображаются,
напишите обычным текстом: «Используй MCP `elemspec` и создай новый UI-тест…».

Codex имеет дополнительный удобный режим:

Удобный режим обычной задачи устанавливается один раз на компьютере:

```bash
elemspec integrate codex
```

Откройте каталог проекта тестов как рабочий корень Codex и создайте новую задачу.
Для технически изолированного режима используйте строгого автора:

```bash
elemspec author check
elemspec author cli
elemspec author exec 'Используй $new-test. Создай тест ...'
```

Команды запускаются внутри проекта тестов. Также можно передать `--project` перед
подкомандой `author`. Документация Codex CLI:
[официальная инструкция](https://learn.chatgpt.com/docs/codex/cli).

## Разработка самого ElemSpec

`.venv` нужна только для изменения исходников движка:

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e .
.venv/bin/python -m playwright install chromium
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests_unit -v
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m unittest discover -s tests_unit -v
```

## Обновление и удаление

После публикации в PyPI:

```bash
pipx upgrade elemspec
elemspec install-browser
```

Из Git URL или локального checkout используйте `pipx reinstall elemspec` либо
повторную установку с `--force`. После обновления повторите установку Codex skill, чтобы
его версия совпадала с движком:

```bash
elemspec integrate codex
```

Удаление:

```bash
elemspec integrate codex --remove
pipx uninstall elemspec
```

Первая команда удаляет только skill и MCP, установленные самим ElemSpec. Проекты
feature-тестов и отчёты при этом не удаляются.

## Диагностика

```bash
elemspec doctor
elemspec --version
elemspec integrate codex --check
```

`doctor` проверяет найденный `elemspec.toml`, каталог тестов и Chromium. Если
проект не найден, перейдите в его каталог или используйте `--project`.

Если Chromium отсутствует:

```bash
elemspec install-browser
```

На Linux при нехватке системных библиотек:

```bash
elemspec install-browser --with-deps
```

Коды CLI:

- `0` — операция или прогон успешны;
- `1` — сценарий упал либо `doctor` не нашёл Chromium;
- `2` — ошибка вызова, проекта или конфигурации.
