# elemspec — совместимость с Claude Code

Канонические агентские инструкции лежат в [AGENTS.md](AGENTS.md). Перед работой прочитать его
целиком. Этот файл оставлен как entry point для сред, которые автоматически ищут
`CLAUDE.md`.

Кратко:

- `elemspec` — отдельный Python/Gherkin/Playwright-инструмент, а не приложение 1С:Элемент;
- установка и зависимости — [docs/installation.md](docs/installation.md);
- движок и роли — [README.md](README.md);
- DSL — [docs/language.md](docs/language.md);
- сборка нового теста идёт только через доверенное ядро/MCP, если среда поддерживает
  контракт `.agents/skills/new-test/`;
- изменение DSL или `src/` — отдельная задача, а не побочный эффект сборки теста.
