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
`разведка`. Открытие дожидается загрузки конечной страницы и сохраняет отдельно
`запрошенный_url`, конечный `url` и `цепочка_url`. Redirect между разрешёнными
hostname подтверждает действие открытия и не является дефектом; конечный адрес
проверять отдельным шагом `адрес содержит "..."`.

Далее вызывать `browser_action` с тем же `browser_session`:

```json
{"browser_session":"<uuid>","operation":"snapshot"}
{"browser_session":"<uuid>","operation":"visible-text","text_limit":20000}
{"browser_session":"<uuid>","operation":"locator-pick","ref":"e4"}
{"browser_session":"<uuid>","operation":"click","ref":"e4"}
{"browser_session":"<uuid>","operation":"hover","ref":"e4"}
{"browser_session":"<uuid>","operation":"fill","ref":"e7","value":"Иван"}
{"browser_session":"<uuid>","operation":"select-html-option","ref":"e8","value":"В статьях"}
{"browser_session":"<uuid>","operation":"select-value","ref":"e7","value":"Москва"}
{"browser_session":"<uuid>","operation":"select-any-value","ref":"e7","value":"Москва"}
{"browser_session":"<uuid>","operation":"read-value","ref":"e7"}
{"browser_session":"<uuid>","operation":"read-field-error","ref":"e7"}
{"browser_session":"<uuid>","operation":"table-row-check","table":"ОсновнаяТаблица","column":"Наименование","value":"Иван"}
{"browser_session":"<uuid>","operation":"table-row-open","table":"ОсновнаяТаблица","column":"Наименование","value":"Иван"}
{"browser_session":"<uuid>","operation":"key","value":"Enter"}
{"browser_session":"<uuid>","operation":"locator-check","locator_kind":"элемент","value":"Результат"}
{"browser_session":"<uuid>","operation":"locator-check","locator_kind":"поле","value":"login-edit"}
{"browser_session":"<uuid>","operation":"locator-check","locator_kind":"команда","value":"Готово"}
{"browser_session":"<uuid>","operation":"locator-check","locator_kind":"команда диалога","value":"Delete"}
{"browser_session":"<uuid>","operation":"locator-check","locator_kind":"пункт навигации","value":"Sales"}
{"browser_session":"<uuid>","operation":"locator-check","locator_kind":"заголовок формы","value":"Clients"}
{"browser_session":"<uuid>","operation":"locator-check","locator_kind":"заголовок диалога","value":"Delete client"}
{"browser_session":"<uuid>","operation":"locator-resolve","locator_kind":"селектор","value":"input[name='email']"}
```

`visible-text` возвращает нормализованный видимый `innerText` страницы и
признак обрезания. Предел `text_limit` — от 1 до 50 000, по умолчанию 20 000.
Значения `input`, включая password-поля, в этот текст не входят; в evidence
сохраняются только длина и признак обрезания. Операция нужна для разведки
неизвестной фразы; шаг feature затем подтверждается точечным `locator-check`.

`locator-resolve` принимает явный локатор, требует ровно одно видимое
совпадение и возвращает новый `ref`. Этот `ref` можно передать в `click`, `hover`,
`fill`, `read-value` и другие ref-операции. Текст и произвольный CSS возвращают
технический долг. Простые CSS-локаторы, различающиеся только кавычками
в атрибуте, считаются тем же evidence.

`snapshot` возвращает отдельный `ref` для каждого видимого
`data-component="navigation-item"`. В полях `текст` и `метка` находится текст
вложенного `data-component="label"`. `locator-pick` возвращает для такого
элемента `{"вид":"пункт навигации","значение":"Sales"}` без технического
долга, если точная метка уникальна. В feature использовать, например,
`Когда я нажимаю пункт навигации "Sales"`. После `hover`, клика или другого
изменения DOM запросить новый `snapshot`.

Если для элемента нет платформенной семантики и `data-testid`, `locator-pick`
пробует стабильные `id`, `name` и `aria-label`. Он вернёт простой
атрибутный CSS без долга. Динамические id, `placeholder`, текст и структурный
CSS остаются резервом с техническим долгом.

`locator-check` дополнительно возвращает `доступных`: число видимых элементов,
которые не отключены native-атрибутом и не имеют `aria-disabled="true"`.

`select-html-option` требует `ref` единственного видимого нативного HTML
`<select>` и точную видимую подпись option в `value`. Отсутствующая, повторяющаяся
или disabled-опция даёт явную ошибку; `<select multiple>` не поддерживается. Ответ
содержит фактическую подпись и низкоуровневый `html_value`. В feature это
`Когда я выбираю "В статьях" в селектор "select[name='search_scope']"`.

Для редактируемого элемента внутри именованного `data-testid` компонента
`snapshot` возвращает `компонент_поля`, а `locator-pick` -
`{"вид":"поле","значение":"login-edit"}` без технического долга.
В feature использовать `Когда я ввожу "..." в поле "login-edit"`.
`read-value` возвращает текущее пользовательское значение поля для шагов
`поле "..." имеет значение "..."` и `поле "..." пусто`. Чтение password-полей
запрещено, чтобы секреты не попадали в evidence. Очистка исследуется операцией
`fill` с пустым `value`.
`read-field-error` возвращает единственное видимое сообщение
`base-editable-message-information` строго внутри именованного компонента поля.
Операция используется для шага `поле "..." имеет ошибку "..."`; ноль сообщений
фиксируется как наблюдаемый факт, а несколько сообщений считаются неоднозначностью.
`select-value` кликает по именованному полю, требует ровно один видимый
`data-testid="edit-dropdown-table"`, выбирает единственную платформенную строку
с точным `value` и возвращает фактическое значение редактора. DOM-копии одной
строки схлопываются только по одинаковому непустому `data-row-index`; разные
логические индексы остаются ошибкой неоднозначности. Результат содержит
`dom_совпадений` и число логических `совпадений`. В feature это
`Когда я выбираю "Москва" в поле "БизнесРегион"`.
`select-any-value` отдельно доказывает фразу `Когда я выбираю любое значение
"Москва" в поле "БизнесРегион"`: несколько логических совпадений разрешены
явно, но отсутствие значения остаётся ошибкой.

Для `data-component="button"` с уникальной точной вложенной
`data-component="label"` `locator-pick` возвращает локатор `команда`. В feature
использовать `Когда я нажимаю команду "Готово"`.

`table-row-check` проверяет строки внутри именованного `data-testid` контейнера
платформенной таблицы. Строки распознаются по `data-component="table-row"`, а
точное значение — в именованной колонке. Результат содержит число совпадений,
видимых строк и их тексты для evidence.
`table-row-open` использует тот же составной локатор и открывает строку только
при единственном совпадении. Для команды внутри видимого `role="alertdialog"`
локатор `команда диалога` ограничивает поиск границей диалога и не конфликтует
с одноимённой командой формы.

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
