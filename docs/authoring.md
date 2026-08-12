# ИИ-автор тестов ElemSpec

Основной интерфейс ИИ-автора — переносимый stdio MCP `elemspec`. Он публикует как
узкие инструменты, так и канонический prompt `new_test`. Поверх него доступны два
режима Codex: обычная задача для ежедневной работы и отдельный строгий CLI, который
технически отключает все инструменты кроме `elemspec mcp`.

## Универсальное подключение

```bash
elemspec mcp-config
elemspec --project /path/to/specs mcp-config  # жёсткая привязка при необходимости
```

Перенесите `command` и `args` в форму добавления MCP-сервера своего клиента. Клиент с
поддержкой MCP prompts получает `new_test` непосредственно от ElemSpec. Для Claude
Code вызов выглядит как `/mcp__elemspec__new_test`; в остальных клиентах имя и меню
зависят от интерфейса. Обычная просьба использовать MCP `elemspec` также работает.

Предусловия:

- ElemSpec установлен через `pipx`, Chromium установлен по [инструкции](installation.md);
- установлен и авторизован Codex CLI;
- целевой hostname есть в `elemspec.toml`.

## Обычная задача Codex

Один раз на компьютере:

```bash
elemspec integrate codex
elemspec integrate codex --check
```

После этого откройте проект тестов как отдельный рабочий корень, создайте новую задачу
и напишите `Используй $new-test`. Skill требует работать только через MCP ElemSpec,
но shell и другие инструменты обычной задачи остаются технически доступными.

Если задача открыта в родительском рабочем каталоге, закрепите проект в MCP явно:

```bash
elemspec --project /absolute/path/to/my-specs integrate codex --force
elemspec --project /absolute/path/to/my-specs integrate codex --check
```

После изменения MCP-конфигурации создайте новую задачу Codex.

## Строгий запуск

`.elemspec/authoring/` внутри выбранного проекта тестов — генерируемый рабочий
каталог отдельного строгого Codex CLI. В нём агент не может писать в файлы,
вызывать shell, web, apps и subagents. Тесты создаются только через `elemspec mcp`.

Из корня независимого проекта feature-тестов:

```bash
elemspec author check
elemspec author cli
```

Можно сразу передать сценарий:

```bash
elemspec author cli 'Используй $new-test. Создай тест ...'
```

Для одной неинтерактивной задачи:

```bash
elemspec author exec 'Используй $new-test. Создай тест ...'
```

Одинарные кавычки не дают Bash попытаться подставить shell-переменную `$new-test`.

## Что генерирует команда

`elemspec author setup` создаёт `.elemspec/authoring/` с абсолютными путями текущей
машины. Каталог не попадает в Git. Файловая авторизация Codex подключается символической
ссылкой, но не копируется.

Профиль фиксирует:

- `sandbox_mode = "read-only"` и `approval_policy = "never"`;
- отключённые shell, web, apps и subagents;
- подключённый `$new-test`;
- единственный MCP-сервер `elemspec` с точным allowlist инструментов.

В официальной модели Codex skill описывает порядок работы, а MCP даёт контролируемые
инструменты и действия: [Skills](https://developers.openai.com/plugins/concepts/skills),
[MCP](https://learn.chatgpt.com/docs/extend/mcp).

Обычная desktop-задача получает skill и MCP через `elemspec integrate codex`, но не
получает этот отдельный профиль прав. Поэтому строгий режим по-прежнему запускается
через CLI.

## Диагностика и восстановление

```bash
elemspec author check
codex doctor
```

`check` проверяет проектный профиль; `codex doctor` — установку, конфигурацию и авторизацию Codex.

Если чат потерян, готовые тесты и отчёты не теряются. Но автоматически найти и продолжить
незавершённую agent session пока нельзя: MCP-инструмент поиска/восстановления ещё в плане.
Откройте новый чат, укажите имя теста и попросите сначала проверить его текущее состояние.
Для незаписанного черновика разведку и сессию придётся повторить.
