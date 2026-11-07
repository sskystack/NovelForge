# NovelForge

[English](README.md) | [简体中文](README.zh-CN.md)

NovelForge is an open-source fiction workspace that keeps story canon author-controlled and versioned. The product direction is **Desktop-Local First**: Windows and macOS are the first release targets, with project data stored on the user's device.

> **Development status:** the repository has backend and web foundations through NF-012, but it is not yet an installable desktop application. NF-010 to NF-012 have implementation gaps recorded in the [roadmap](docs/ROADMAP.md). There is no Tauri shell, packaged Python sidecar, production SQLite profile, FTS5 index, or installer yet.

## Current status

- Implemented foundations: identity and novel ownership, canon CRUD and approval history, outlines and chapters, immutable chapter versions, connected web editor, provider interfaces, knowledge ingestion/search prototypes, and a context compiler.
- Verified locally at the latest audited commit (`27360af`): 57 API tests passed; latest GitHub CI passed. These results do not establish desktop packaging or full NF-010 to NF-012 acceptance.
- The audit found no GitHub Issues before synchronization; tracking Issues #1–#10 are now open for NF-013–NF-022. Their labels and deferred status are part of the current evidence; see [ROADMAP.md](docs/ROADMAP.md).
- Supported today: developer-run API and web app. Planned first-class installs: Windows x64 EXE and macOS DMG. Android and remote SaaS/self-hosting are deferred.

## Desktop target

The intended desktop stack is React + Vite, Tauri 2, a bundled FastAPI Python sidecar, SQLAlchemy/Alembic, and SQLite in the per-user application data directory. SQLite FTS5 is the planned lexical index. Model API credentials will be configured locally and kept out of browser bundles and logs. The sidecar must bind only to loopback, use local request authorization, start and stop with the desktop app, and preserve user data through upgrades.

This is a target architecture, not a claim about current functionality. Vector retrieval remains behind an adapter. The current prototype stores embeddings as JSON and computes cosine scores in Python; FTS5 and packaged vector options require an explicit design/test issue before implementation.

## Developer setup today

Prerequisites for the current source workflow: Python 3.12+, `uv`, Node.js 20+, npm, and GNU Make (optional). The current API defaults to PostgreSQL; the test suite uses SQLite. This development setup is not the end-user desktop installation path.

```sh
./scripts/setup.sh
make dev-api       # API health: http://127.0.0.1:8000/health
make dev-web       # Web UI: http://localhost:5173
make test
make lint
make typecheck
```

Windows PowerShell setup: `./scripts/setup.ps1`. The scripts install development dependencies; they do not create a desktop installer or bundle Python/Node runtimes.

## Project documents

- [Roadmap and audited status](docs/ROADMAP.md)
- [Product requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Database design](docs/DATABASE.md)
- [API contract](docs/API.md) and [OpenAPI file](openapi.yaml)
- [Agent and retrieval specification](docs/AGENT_SPEC.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Platform packaging plan](docs/PLATFORM_PACKAGING.md)
- [Engineering backlog](docs/GITHUB_ISSUES.md)

Cloud SaaS, self-hosted server release, Android and multi-device sync remain in the backlog as deferred work; they are not current release targets.

## License

Apache-2.0 is the target license; a repository license file has not yet been added.
