# NovelForge

[English](README.md) | [简体中文](README.zh-CN.md)

NovelForge is an open-source fiction workspace that keeps story canon author-controlled and versioned. The product direction is **Desktop-Local First**: Windows and macOS are the first release targets, with project data stored on the user's device.

> **Development status (2026-11-20):** the recovered Tauri desktop source now builds a macOS Apple Silicon 0.1.1 DMG with a frozen Python sidecar and versioned SQLite initialization. Native UI and packaged-service workflows have been checked. FTS5, a complete agent execution loop, and MCP integration remain follow-up work. The [roadmap](docs/ROADMAP.md) retains the earlier audit history.

## Current status

- Implemented foundations: identity and novel ownership, canon CRUD and approval history, outlines and chapters, immutable chapter versions, connected web editor, provider interfaces, knowledge ingestion/search prototypes, and a context compiler.
- Current local checks: 83 API tests, 19 frontend tests, and 12 packaged-service workflow checks passed. Native UI checks cover authentication, Chinese projects and chapters, editing, format conversion, generation previews and acceptance, version restoration, analysis, persistence across restart, and logout. Model tests use deterministic mocks and a local protocol stub, without paid model requests.
- The audit found no GitHub Issues before synchronization; tracking Issues #1–#10 are now open for NF-013–NF-022. Their labels and deferred status are part of the current evidence; see [ROADMAP.md](docs/ROADMAP.md).
- Verified artifact: macOS Apple Silicon DMG with ad-hoc signing. Developer ID signing and notarization are not configured. Windows packaging is retained but was not exercised on a Windows host in this work. Android and remote SaaS/self-hosting remain deferred.

## Desktop target

The intended desktop stack is React + Vite, Tauri 2, a bundled FastAPI Python sidecar, SQLAlchemy/Alembic, and SQLite in the per-user application data directory. SQLite FTS5 is the planned lexical index. Model API credentials will be configured locally and kept out of browser bundles and logs. The sidecar must bind only to loopback, use local request authorization, start and stop with the desktop app, and preserve user data through upgrades.

The desktop runtime path is implemented; see [Desktop README](apps/desktop/README.md) for builds and local configuration. Retrieval remains a prototype: embeddings are stored as JSON and cosine scores are computed in Python. FTS5 and a packaged vector index still require implementation and evaluation.

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
