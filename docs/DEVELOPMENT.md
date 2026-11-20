# NovelForge — Development Guide

> **Owner decision — 2026-11-20: macOS only.** Android, Windows and other platforms are no longer maintained, built or released. Historical multi-platform plans below do not authorize new work or create acceptance gates. Read the repository `AGENTS.md` first; current Agent/RAG/MCP implementation evidence is in `docs/AGENT_GAP_ANALYSIS.md`.

The maintained Tauri macOS app, frozen Python sidecar, and SQLite runtime are implemented. Use `./script/build_and_run.sh` (also Codex Run) for the native build/run loop, with ignored `.local-data/` development fixtures. Optional flags are `--logs`, `--debug`, `--telemetry` and `--verify`.

## 1. Repository layout

```text
novelforge/
├── apps/
│   ├── api/
│   │   ├── novelforge/
│   │   │   ├── identity/
│   │   │   ├── projects/
│   │   │   ├── canon/
│   │   │   ├── planning/
│   │   │   ├── manuscripts/
│   │   │   ├── knowledge/
│   │   │   ├── ai/
│   │   │   ├── tools/
│   │   │   ├── consistency/
│   │   │   └── jobs/
│   │   ├── alembic/
│   │   └── tests/
│   └── web/
│       ├── src/
│       ├── components/
│       ├── features/
│       └── tests/
├── apps/desktop/          # Tauri 2 desktop shell
├── apps/mobile/           # historical, unmaintained Android scaffold
├── packages/
│   └── shared-contracts/
├── db/
├── docs/
├── scripts/              # setup, dev, build, package, migration
├── .github/
└── Makefile
```

## 2. Backend conventions

- Python 3.12+.
- Type hints on public functions.
- Pydantic schemas at API and provider boundaries.
- SQLAlchemy 2 async or sync consistently; do not mix patterns within a module.
- Alembic for all schema changes.
- Domain services own business rules; routers stay thin.
- Repository methods require explicit `NovelScope`.
- Avoid generic `dict` for domain entities; use typed models.
- Use structured logging with request and generation IDs.

## 3. Frontend conventions

- React + Vite + TypeScript strict mode; shared UI bundle for web and Tauri shells.
- TipTap JSON is the rich-text canonical format.
- Markdown mode must have explicit parse/serialize behavior and round-trip tests.
- Autosave uses debounce plus optimistic concurrency.
- AI output is previewed as a diff/insert operation.
- Never replace editor content without user action.
- Keep provider secrets out of client-side code.

## 4. Testing pyramid

### Unit
- domain validation
- state transitions
- context precedence
- chunking and retrieval filters
- tool permission checks
- Markdown/Tiptap conversion

### Integration
- SQLite migration, optional FTS5 and exact vector retrieval
- novel-scope repository enforcement
- chapter version conflict
- canon approval transaction
- provider adapter contract
- ingestion and re-index lifecycle

### E2E
- create novel
- add character and world rule
- create outline and chapter
- switch rich/Markdown
- run AI generation using a mock provider
- inspect sources
- accept draft
- propose and approve canon update
- export/import round-trip

### Security regression
- cross-novel API access
- cross-novel RAG search
- cross-novel tool invocation
- unauthorized canon write
- archive path traversal
- prompt injection in retrieved text
- secret leakage in logs

## 5. Local development

1. Copy `.env.example` to `.env`.
2. Run macOS setup; install Python and Node.js for source development. Docker is not required.
3. The native runtime selects per-user file-backed SQLite and applies migrations. The browser development API uses a separately configured database.
4. Start FastAPI and Vite using the task runner.
5. Configure a mock provider for tests.
6. Build the native macOS application with the Run script or `npm run tauri:build --prefix apps/desktop`. Android and Windows are no longer maintained.

For the current source workflow, copy `.env.example` to `.env`, configure `DATABASE_URL` for a local development database, then run `uv run --directory apps/api alembic -c alembic.ini upgrade head`. The checked-in default still points to PostgreSQL; the native app selects a supported SQLite profile automatically. Use `SESSION_COOKIE_SECURE=false` only for plain HTTP localhost development.

## 6. CI gates

- format/lint
- type checks
- unit tests
- SQLite integration and migration tests; PostgreSQL checks belong to the deferred server profile
- frontend tests
- Playwright smoke tests
- migration validation
- dependency and secret scanning
- macOS frozen-sidecar, signed bundle and DMG smoke tests
- no Android or Windows release gates

## 7. Definition of Done

A task is complete only when:
- acceptance criteria are met
- tests cover normal and failure paths
- authorization is enforced
- migrations are included if schema changes
- docs/API contracts are updated
- no secrets or real manuscript data are committed
- CI passes
