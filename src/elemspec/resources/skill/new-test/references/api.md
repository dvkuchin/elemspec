# MCP API elemspec

Вызывать только инструменты MCP-сервера `elemspec`. Каждый ответ содержит
`mcp_api_version`, `agent_api_version`, `elemspec_version` и `result`.

## Получить контракт

Вызвать `get_contract()`.

## Проверить черновик без записи

Вызвать `validate_draft(test_name, init_json, feature)`:

```json
{
  "test_name": "имя-теста",
  "init_json": "{\"базовый_адрес\":\"https://test.example\"}",
  "feature": "# language: ru\nФункция: ...\n"
}
```

## Браузерная сессия

Вызвать `browser_start(url)`. Ответ содержит `browser_session` и UUID
`разведка`. Далее вызывать `browser_action` с тем же `browser_session`:

```json
{"browser_session":"<uuid>","operation":"snapshot"}
{"browser_session":"<uuid>","operation":"locator-pick","ref":"e4"}
{"browser_session":"<uuid>","operation":"click","ref":"e4"}
{"browser_session":"<uuid>","operation":"fill","ref":"e7","value":"Иван"}
{"browser_session":"<uuid>","operation":"key","value":"Enter"}
{"browser_session":"<uuid>","operation":"locator-check","locator_kind":"элемент","value":"Результат"}
```

После изменения DOM запрашивать новый snapshot; старые `ref` не считать
актуальным доказательством.

После разведки вызвать `browser_close(browser_session)`. UUID `разведка`
передать в `prepare_draft`. Журнал хранится ядром; модель не формирует
evidence самостоятельно.

## Сессия записи

`start_session(test_name)` возвращает `сессия`.

`prepare_draft`:

```json
{
  "session_id": "<uuid>",
  "discovery_id": "<uuid из browser>",
  "init_json": "<полный JSON строкой>",
  "feature": "<полный feature строкой>"
}
```

`prepare_draft` может вернуть:

- `UNVERIFIED` — перечислены шаги без browser evidence, запись запрещена;
- `BUG_FOUND` / `AWAITING_BUG_CONFIRMATION` — expected расходится с actual;
- `APPLIED` — новый подтверждённый тест записан;
- `AWAITING_CONFIRMATION` — изменение существующего теста ждёт diff-confirmation.

`apply_draft` для существующего теста:

```json
{"session_id":"<uuid>","draft_revision":"<sha256 из prepare_draft>"}
```

`apply_draft` для подтверждённого автором дефекта:

```json
{
  "session_id":"<uuid>",
  "draft_revision":"<sha256 из prepare_draft>",
  "confirm_bug":true
}
```

## Зарегистрировать дыру языка

Feature обязан содержать:

```gherkin
# ТЗ: engine-gap:table-row-cell-value
```

Вызвать `register_engine_gap(session_id, gap)`. Поле `gap`:

```json
{
  "id": "table-row-cell-value",
  "предлагаемая_фраза": "...",
  "назначение": "...",
  "проверено_в_приложении": {
    "поведение": "...",
    "локаторы": ["..."]
  },
  "аргументы": ["..."],
  "семантика": {
    "ок": "...",
    "провал": "...",
    "сломан": "..."
  },
  "ожидание": "...",
  "примеры": {
    "позитивный": "...",
    "негативный": "...",
    "неоднозначный": "..."
  },
  "критерии_готовности": ["..."]
}
```

Полная схема: `engine-gaps/schema.json`.

## Доказать зелёный-красный-зелёный

Вызвать `prove_test(session_id)`.

Итоговые статусы: `COMPLETE`, `COMPLETE_WITH_GAPS`, `BUG_CONFIRMED`.
Последний означает доказанное воспроизведение реального дефекта, а не зелёный
тест.
