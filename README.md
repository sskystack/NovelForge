# NovelForge

[English](README.md) | [简体中文](README.zh-CN.md)

NovelForge is an open-source fiction workspace that keeps story canon author-controlled and versioned. Effective 2026-11-20, **macOS is the only maintained product platform**. Android, Windows and other platforms are no longer maintained or released. Read the repository [AGENTS.md](AGENTS.md) before making changes.

> **Development status (2026-11-20):** the recovered Tauri desktop source now builds a macOS Apple Silicon 0.1.1 DMG with a frozen Python sidecar and versioned SQLite initialization. Native UI and packaged-service workflows have been checked. 0.2.0 adds the writing workspace, durable agent loop, function calling, FTS5/RAG, MCP SDK and local model settings; see [the evidence and remaining limits](docs/AGENT_GAP_ANALYSIS.md). The [roadmap](docs/ROADMAP.md) retains earlier audit history and is superseded by the macOS-only maintenance decision.

## Current status

- Implemented foundations: identity and novel ownership, canon CRUD and approval history, outlines and chapters, immutable chapter versions, connected web editor, provider interfaces, knowledge ingestion/search prototypes, and a context compiler.
- Current local checks: 118 API tests, 47 frontend tests, 6/6 deterministic retrieval regressions and 16 frozen-sidecar workflow checks passed. Native UI checks cover authentication, Chinese projects and chapters, editing, format conversion, generation previews and acceptance, version restoration, analysis, persistence across restart, and logout. Model tests use deterministic mocks and a local protocol stub, without paid model requests.
- The audit found no GitHub Issues before synchronization; tracking Issues #1–#10 are now open for NF-013–NF-022. Their labels and deferred status are part of the current evidence; see [ROADMAP.md](docs/ROADMAP.md).
- Verified artifact: macOS Apple Silicon DMG with ad-hoc signing. Developer ID signing and notarization are not configured. Android/Windows scaffolds are historical and carry no testing or release commitment. Remote SaaS is outside the current product scope.

## Desktop target

The intended desktop stack is React + Vite, Tauri 2, a bundled FastAPI Python sidecar, SQLAlchemy/Alembic, and SQLite in the per-user application data directory. Optional SQLite FTS5 is the lexical index. Model API credentials are configured in local settings and kept out of browser bundles and logs. They are currently stored in a permission-restricted local database; OS Keychain encryption is not yet implemented. The sidecar must bind only to loopback, use local request authorization, start and stop with the desktop app, and preserve user data through upgrades.

The desktop runtime path is implemented; see [Desktop README](apps/desktop/README.md) for builds and local configuration. Retrieval remains a prototype: embeddings are stored as JSON and cosine scores are computed in Python. FTS5 is implemented; large-corpus ANN, reranking and semantic quality require real model/corpus evaluation. Mock output is an offline demonstration.

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

Use `./script/build_and_run.sh` for the native macOS development loop and Codex Run action, with ignored `.local-data/` fixtures. `npm run tauri:build --prefix apps/desktop` builds the standalone application. The PowerShell script is unsupported historical material.

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

Android, Windows and other platforms are outside the maintained scope; historical backlog entries are not support commitments. Cloud SaaS and multi-device sync are not current release targets.

## License

Apache-2.0 is the target license; a repository license file has not yet been added.
