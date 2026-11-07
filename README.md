# NovelForge

NovelForge is an open-source workspace for planning and writing long-form fiction with AI while keeping canonical story facts author-controlled and versioned.

## Project status

The repository is being built issue by issue from the [engineering backlog](docs/GITHUB_ISSUES.md). NF-001 provides the modular-monolith skeleton and local development tooling; product modules are not implemented yet.

## Requirements

- Python 3.12+
- Node.js 20+ and npm
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16+ with pgvector for server development (install natively; Docker is not required)
- GNU Make is optional; the setup scripts also work directly

PostgreSQL installation: on macOS, `brew install postgresql@16` and `brew install pgvector`; on Ubuntu, install PostgreSQL 16 and the matching `postgresql-16-pgvector` package from the PostgreSQL/PGDG repository; on Windows, use the PostgreSQL 16 installer and install the matching pgvector extension. Start PostgreSQL, create a local `novelforge` database and role, then configure `DATABASE_URL` in `.env`. Database migrations and database-backed functionality are introduced by later issues.

## Setup

1. Copy `.env.example` to `.env` and adjust local database values.
2. Run the setup script for your operating system:

   ```sh
   # macOS / Linux
   ./scripts/setup.sh
   ```

   ```powershell
   # Windows PowerShell
   .\scripts\setup.ps1
   ```

The scripts validate prerequisites and install locked API and web dependencies. They do not install or configure PostgreSQL for you.

## Run and test

```sh
make dev-api       # http://127.0.0.1:8000/health
make dev-web       # http://localhost:5173
make test          # API and web tests
make lint          # Ruff and ESLint
make typecheck     # TypeScript strict checks
```

Commands can also be run without Make:

```sh
uv run --directory apps/api uvicorn novelforge.main:app --reload
uv run --directory apps/api pytest
cd apps/web && npm run dev
cd apps/web && npm test
```

## Architecture and contracts

The backend is a modular monolith. PostgreSQL + pgvector is the server baseline; SQLite + FTS5 is reserved for the desktop-local profile and must remain behind database/retrieval adapters. Redis is optional for local development. Novel-scoped access, immutable canon revisions, RAG provenance, and human approval are required by the specifications.

- [Product requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Database design](docs/DATABASE.md)
- [API](docs/API.md) and [OpenAPI contract](openapi.yaml)
- [Agent, RAG and Context Compiler](docs/AGENT_SPEC.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Platform packaging](docs/PLATFORM_PACKAGING.md)
- [Engineering backlog](docs/GITHUB_ISSUES.md)
- [Initial PostgreSQL schema](db/schema.sql)

## License

Apache-2.0 (target license; the repository license file will be added with the licensing issue).
