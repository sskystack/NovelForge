# NovelForge Desktop-Local First Roadmap

> **Owner decision — 2026-11-20: macOS only.** Android, Windows and other platforms are no longer maintained, built or released. Historical multi-platform plans below do not authorize new work or create acceptance gates. Read the repository `AGENTS.md` first; current Agent/RAG/MCP implementation evidence is in `docs/AGENT_GAP_ANALYSIS.md`.

**Status date:** 2026-11-07
**Audited revision:** `27360af` (`main`)
**Product priority:** Windows and macOS desktop, single-device local data
**Audit boundary:** source, tests, docs, commit history, GitHub Actions and GitHub Issues

## Product direction

The first deliverable is an installable Windows/macOS fiction-writing application. It must start without the user installing Python, Node.js, PostgreSQL or Docker; store projects under the user's local application data directory; preserve data across close/reopen and upgrades; support backup, restore and project export; and use a bundled FastAPI sidecar restricted to loopback. AI connects only to a model endpoint explicitly configured by the user. Web remains the shared development UI. SaaS, remote self-hosted deployment, Android and multi-device sync are deferred.

Target stack: React + Vite, Tauri 2, packaged Python/FastAPI sidecar, SQLAlchemy/Alembic, SQLite and SQLite FTS5. This describes the target, not the repository's current runtime.

## Audited repository status

The `main` branch contains issue-shaped commits through NF-012. All 13 CI runs visible at audit time for NF-001 through NF-012 were successful except the initial NF-001 run, which was cancelled and followed by a successful cleanup run. Local verification reported 57 API tests passing at `27360af`. The latest CI run for NF-012 was [42377901767](https://github.com/sskystack/NovelForge/actions/runs/42377901767).

The repository had **zero GitHub Issues** at audit time. `docs/GITHUB_ISSUES.md` was the only backlog record; no remote issue had been opened or closed. The plan has since created tracking Issues #1–#10 for NF-013–NF-022; none of those implementation issues is closed. Therefore NF-001–NF-012 status below is based on code/tests/docs and commit/CI evidence, while the new issue state is independently visible in GitHub.

| NF | Audited status | Evidence-based qualification |
|---|---|---|
| 001 | Implemented foundation | Monorepo, setup scripts and CI exist. The end-user desktop install criteria remain unfulfilled. |
| 002 | Implemented foundation | Local user/session auth and owner-scoped novel routes with tests. No remote identity service is required by this local-first direction. |
| 003 | Implemented | Novel-scoped canon models, migration, CRUD and isolation tests. |
| 004 | Implemented | Story events, character state, relationships and story-time queries with tests. |
| 005 | Implemented | Nested outline/chapter metadata and tests. |
| 006 | Implemented | Immutable chapter versions, ETag concurrency and tests. |
| 007 | Implemented web workflow | Web editor connects to APIs and tests. It is not a packaged desktop app. |
| 008 | Implemented | Canon proposal, approval/rejection, revision and restore workflow with tests. |
| 009 | Implemented provider foundation | Deterministic mock and OpenAI-compatible adapter exist. Provider settings are environment configuration; there is no desktop settings UI or credential store. |
| 010 | Partial; acceptance gap | Provenance models and synchronous chunk/embedding service exist. There is no ingestion route or durable background/retry job. Embeddings are JSON. |
| 011 | Partial; acceptance gap | Novel/visibility filters, Python lexical/cosine scoring and RRF exist. There is no SQLite FTS5 or pgvector query; the implementation loads candidate chunks into Python memory. API tests cover scoping/fallback, not a full retrieval evaluation. |
| 012 | Partial; acceptance gap | SQLite-backed deterministic packet tests exist. Approved-fact conflict detection is absent; recent-chapter count is unused; query retrieval invokes lexical-only search without the configured embedding provider. |
| 013-017 | Not started | Present in the source backlog only at the audited revision. |
| 018 | Deferred | Self-hosted server release is outside current scope. |
| 019 | Not started; release target | No Tauri project, sidecar packaging, installer workflow or app lifecycle integration exists. |
| 020 | Deferred | Android is outside current scope. |

SQLite is used by automated API tests, and the Alembic chain has been exercised on SQLite. However, `Settings.database_url` and `alembic.ini` default to PostgreSQL, `psycopg` is a required dependency, no production local database path is configured, and no FTS5 virtual table exists. SQLAlchemy JSON variants and existing ORM queries are largely portable, but that is not equivalent to a verified, supported SQLite desktop profile.

Current API user/session records are stored in the configured local database. There is no remote auth provider. The OpenAI-compatible adapter sends requests to an external model endpoint only when configured. In the source workflow the CI and development commands use loopback defaults, but the application does not yet supervise a desktop sidecar, mint per-launch credentials or enforce a packaged-app binding policy.

## Local vector retrieval options

| Option | Runtime/performance | Packaging and maintenance | Migration impact |
|---|---|---|---|
| Bounded exact cosine through the existing provider-neutral adapter | No native dependency; O(number of candidate chunks × vector dimensions), simple and adequate only for a measured modest local corpus | Lowest build and support cost; predictable Windows/macOS behavior | Keep vectors as derived data with model/dimension metadata; can rebuild from source documents |
| `sqlite-vec` SQLite extension | SQL KNN avoids loading/scoring every vector in Python; performance depends on corpus, dimensions and extension version | Native extension must be built, signed/loaded safely and tested for each platform/SQLite ABI; adds release and upgrade responsibility | Store source and embedding model/version independently; rebuild extension index from source/vector payload if schema changes |
| `hnswlib`/similar embedded ANN index | Fast approximate nearest-neighbor after index build | Native wheels and separate index files complicate sidecar packaging, backup, atomic replacement and crash recovery | Index is derived and rebuildable, but consistency/rollback logic is required across SQLite and index files |
| PostgreSQL + pgvector | Server-grade indexed vector search | Requires a database service, contrary to standalone install requirements | Keeps the current server schema path but cannot be the desktop runtime |

**Recommendation for review:** first ship SQLite FTS5 plus an adapter-backed exact cosine implementation, with corpus-size and latency benchmarks and a documented threshold. Keep embeddings and provenance in SQLite as rebuildable derived data. Adopt `sqlite-vec` only if benchmarks show the exact implementation misses the local corpus target; do not make a separate vector database a desktop prerequisite. This is a proposal pending user approval, not an implementation decision.

## Proposed execution order

1. **NF-021 — Local SQLite, FTS5 and NF-010–012 acceptance gaps.** Establish a supported file-backed SQLite profile, repository/search adapter boundaries, FTS5 indexing, lexical/vector retrieval tests, ingestion endpoint/retry semantics, provenance, context conflicts and recent-chapter behavior. Design migrations and data backup/upgrade behavior before changing existing schemas.
2. **NF-013 — Permissioned tool registry.** Implement read/draft/propose tools against novel-scoped services; no arbitrary SQL/shell and no network queue dependency.
3. **NF-016 — Project export/import.** Move ahead of installer work; add archive checksums/path/size validation, ID remapping, backup and restore without overwrite.
4. **NF-014 — Generation sessions and chapter draft preview.** Use an in-process local execution path first; generation output remains a preview until explicit acceptance with optimistic concurrency.
5. **NF-015 — Post-chapter analysis proposals.** Process immutable chapter versions idempotently; facts remain proposals until approval.
6. **NF-017 — Consistency checks.** Implement deterministic evidence-linked checks and review states; no automatic canon edits.
7. **NF-022 — Desktop sidecar lifecycle and loopback security.** Define port selection, local authentication, health handshake, bounded crash recovery, clean shutdown, log redaction and OS data paths.
8. **NF-019 — Tauri shell and release artifacts.** Package and smoke-test Windows x64 EXE and macOS DMG on native CI runners; prove restart/upgrade persistence and no-runtime-prerequisite installation.
9. Keep **NF-018** and **NF-020** deferred. Reconsider only after the local desktop release gates pass and the product direction is explicitly revisited.

NF-013/016/017 may proceed in parallel after NF-021 interfaces are agreed. NF-014 depends on NF-013 and NF-012 acceptance; NF-015 depends on NF-014 and NF-008; NF-019 depends on NF-016, NF-021, NF-022 and completion of the core workflows.

## Synchronization rules

- No issue is closed solely because its commit exists. Its acceptance tests and evidence must pass.
- Each completed issue updates `README.md` and `README.zh-CN.md` when user-visible status/setup changes, this roadmap, relevant design/API docs, and its GitHub issue.
- Deferred issues remain open with a `deferred` label and a reason. Their source backlog entries remain intact.
- At audit time the GitHub issue list was empty. Tracking Issues #1–#10 now cover NF-013–NF-022; historical NF-001–NF-012 were not bulk-created or closed by this synchronization.
