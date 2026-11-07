# NovelForge — Development Guide

**Product priority:** Desktop-Local First. Windows/macOS installers are not implemented yet. This guide distinguishes today's source-development setup from the planned local runtime.

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
├── apps/mobile/           # Tauri 2 Android target
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
- PostgreSQL and pgvector
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
2. Run OS-specific setup; install Python and Node.js for source development. Docker is not required.
3. The audited default API configuration targets PostgreSQL; automated API and migration tests use SQLite. A supported desktop SQLite profile is planned under NF-021.
4. Start FastAPI and Vite using the task runner.
5. Configure a mock provider for tests.
6. Desktop installers and Android APK cannot yet be built; their application targets are not implemented.

For the current source workflow, copy `.env.example` to `.env`, configure `DATABASE_URL` for a local development database, then run `uv run --directory apps/api alembic -c alembic.ini upgrade head`. The checked-in default still points to PostgreSQL; SQLite has test coverage but is not yet the supported end-user profile. Use `SESSION_COOKIE_SECURE=false` only for plain HTTP localhost development.

## 6. CI gates

- format/lint
- type checks
- unit tests
- SQLite integration and migration tests; PostgreSQL checks belong to the deferred server profile
- frontend tests
- Playwright smoke tests
- migration validation
- dependency and secret scanning
- Windows/macOS desktop package build smoke tests
- Android APK build smoke test (deferred)

## 7. Definition of Done

A task is complete only when:
- acceptance criteria are met
- tests cover normal and failure paths
- authorization is enforced
- migrations are included if schema changes
- docs/API contracts are updated
- no secrets or real manuscript data are committed
- CI passes
