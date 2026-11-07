# NovelForge — First Engineering Backlog

Labels: `epic`, `backend`, `frontend`, `database`, `ai`, `rag`, `security`, `docs`, `good first issue`.

Each issue below is intended to be assigned independently to an AI coding agent after dependencies are met. Do not ask the agent to implement future issues opportunistically.

---

## NF-001 — Initialize monorepo and development tooling

**Labels:** epic, backend, frontend, docs  
**Priority:** P0  
**Depends on:** none

### Goal
Create the repository skeleton and reproducible local development environment.

### Tasks
- Create `apps/api`, `apps/web`, `apps/desktop`, `apps/mobile`, `docs`, `db`, `scripts`.
- Configure Python project with FastAPI, Pydantic, SQLAlchemy, Alembic and Pytest.
- Configure React + Vite TypeScript strict mode, Tailwind and linting.
- Add OS-aware setup scripts and task runner; document direct PostgreSQL installation for server development. Docker must not be required.
- Add `.env.example`; ensure secrets are never committed.
- Add Makefile or task runner commands.

### Acceptance criteria
- A fresh developer environment can be initialized with documented scripts without Docker.
- API health endpoint returns 200.
- Web app starts.
- Backend and frontend test commands run in CI.
- README contains exact setup instructions.

### Tests
- CI smoke test for API health.
- Setup-script validation on supported CI runners.

---

## NF-002 — Implement identity and novel project ownership

**Labels:** backend, database, security  
**Priority:** P0  
**Depends on:** NF-001

### Goal
Implement user authentication baseline and novel project CRUD with strict ownership.

### Tasks
- Add users and novels models/migrations.
- Implement registration/login/logout/me (secure password hashing; secure cookies).
- Implement create/list/get/update/archive novel.
- Ensure every route verifies authenticated ownership.
- Add request schemas and response schemas.

### Acceptance criteria
- User A cannot read, update or archive User B's novel.
- Archived novels are hidden from normal listing but recoverable by policy.
- Passwords are never stored or logged in plaintext.
- API returns consistent problem-detail errors.

### Tests
- Auth flow.
- Cross-user access attempts.
- Invalid input and duplicate email.

---

## NF-003 — Establish canon entity model and CRUD

**Labels:** backend, database  
**Priority:** P0  
**Depends on:** NF-002

### Goal
Implement characters, locations, factions and world rules as novel-scoped entities.

### Tasks
- Add SQLAlchemy models and Alembic migrations.
- Implement CRUD services and API routes.
- Add `canon_status` enum: draft, proposed, canon, deprecated.
- Enforce child entity belongs to path novel.
- Add stable entity identifiers and timestamps.

### Acceptance criteria
- CRUD works for all four entity types.
- A resource ID from another novel cannot be accessed through current novel path.
- Draft/proposed records are not returned as canon by default.
- API contract tests exist.

---

## NF-004 — Add character states and relationships

**Labels:** backend, database  
**Priority:** P0  
**Depends on:** NF-003

### Goal
Represent stable character identity separately from time-dependent story state.

### Tasks
- Add character state snapshots with story order and optional event links.
- Add typed relationships between characters/entities.
- Support validity intervals.
- Add query for character state at a requested story order.
- Prevent invalid cross-novel links.

### Acceptance criteria
- Query at story order N returns applicable state.
- Closed validity intervals are respected.
- Relationship endpoints must belong to the same novel.
- Tests cover flashback/nonlinear story ordering.

---

## NF-005 — Implement nested outline and chapter domain

**Labels:** backend, database  
**Priority:** P0  
**Depends on:** NF-002

### Goal
Implement book/volume/arc/chapter outline hierarchy and manuscript chapter records.

### Tasks
- Add outline nodes with parent ID, node type, ordering and summary.
- Add chapters with title, status, order and linked outline node.
- Validate parent-child hierarchy and prevent cycles.
- Implement CRUD and reorder operations.

### Acceptance criteria
- Arbitrary supported outline depth can be retrieved as a tree.
- Cycles and cross-novel parent links are rejected.
- Reordering is deterministic.
- Pagination is supported for chapter lists.

---

## NF-006 — Implement chapter versioning and optimistic concurrency

**Labels:** backend, database, security  
**Priority:** P0  
**Depends on:** NF-005

### Goal
Prevent lost updates and preserve immutable chapter versions.

### Tasks
- Add chapter_versions table.
- Add version counter to chapters.
- Implement update endpoint requiring expected version / If-Match.
- Return 409 on stale writes.
- Implement restore-as-new-version (never mutate historical version).

### Acceptance criteria
- Two concurrent edits from same version cannot silently overwrite each other.
- Restore creates a new current version.
- Historical versions are immutable.
- Tests simulate concurrent updates.

---

## NF-007 — Build manuscript editor with rich-text and Markdown modes

**Labels:** frontend  
**Priority:** P0  
**Depends on:** NF-005, NF-006

### Goal
Provide a usable chapter editor supporting TipTap and Markdown.

### Tasks
- Build chapter list and editor page.
- Implement TipTap JSON editing.
- Implement Markdown source mode.
- Implement conversion and explicit handling of unsupported constructs.
- Add debounced autosave with optimistic concurrency.
- Add unsaved-change indicator and conflict UI.

### Acceptance criteria
- User can switch modes without silent content loss.
- Round-trip tests cover headings, paragraphs, emphasis, lists, quotes and links.
- Stale save displays conflict and preserves local draft.
- AI-generated text is not inserted without user action.

---

## NF-008 — Add canon revisions and approval workflow

**Labels:** backend, database, security  
**Priority:** P0  
**Depends on:** NF-003, NF-004

### Goal
Make canon changes auditable and author-controlled.

### Tasks
- Add canon_revisions table.
- Implement proposal, approve and reject operations.
- Approval writes entity update and revision in one transaction.
- Store actor, before/after values and reason.
- Add restore by creating a new revision.

### Acceptance criteria
- AI proposal cannot update canon directly.
- Approval requires authorized user action.
- Rejected proposal never changes canonical records.
- Revision history is immutable and queryable.

---

## NF-009 — Implement model provider abstraction and mock provider

**Labels:** ai, backend  
**Priority:** P0  
**Depends on:** NF-001

### Goal
Create vendor-neutral chat and embedding interfaces.

### Tasks
- Define ChatProvider and EmbeddingProvider protocols.
- Implement deterministic MockProvider for tests.
- Implement one real provider adapter behind configuration.
- Normalize tool calls, structured output, streaming and usage metadata.
- Store provider secrets server-side only.

### Acceptance criteria
- Business services depend on interfaces, not vendor SDKs.
- Mock provider enables deterministic CI tests.
- Provider timeout and malformed response are handled.
- API keys never appear in frontend bundles or logs.

---

## NF-010 — Implement knowledge ingestion and chunk provenance

**Labels:** rag, backend, database  
**Priority:** P0  
**Depends on:** NF-003, NF-005, NF-006

### Goal
Ingest canon records and chapter versions into a searchable knowledge index.

### Tasks
- Add knowledge_documents and knowledge_chunks.
- Implement chunker preserving chapter/section boundaries.
- Store source ID, source revision, novel ID and chunker version.
- Implement embedding job with retry/idempotency.
- Mark stale chunks inactive only after successful replacement.

### Acceptance criteria
- Re-ingestion of same source revision is idempotent.
- Every chunk resolves to its source.
- Failed embedding does not delete prior active index.
- No chunk can be indexed without novel scope.

---

## NF-011 — Implement hybrid retrieval with hard novel filters

**Labels:** rag, backend, security  
**Priority:** P0  
**Depends on:** NF-010

### Goal
Search relevant story material using PostgreSQL full-text and pgvector.

### Tasks
- Implement lexical search.
- Implement vector search.
- Apply novel and visibility filters before ranking.
- Merge rankings using reciprocal rank fusion.
- Return snippets and provenance.
- Add query limits and timeouts.

### Acceptance criteria
- Search returns source IDs and revisions.
- Cross-novel retrieval tests return zero foreign results.
- Search remains functional when embeddings are unavailable (lexical fallback).
- Ranking behavior is covered by fixture-based tests.

---

## NF-012 — Build Context Compiler

**Labels:** ai, rag, backend  
**Priority:** P0  
**Depends on:** NF-004, NF-005, NF-010, NF-011

### Goal
Compile a bounded, traceable context packet for a writing task.

### Tasks
- Load current chapter and outline.
- Fetch structured canon and character states at story time.
- Retrieve relevant narrative chunks.
- Apply source precedence and identify conflicting canon.
- Deduplicate and enforce token budget.
- Return citations and warnings.

### Acceptance criteria
- Canon facts are distinguishable from retrieved prose and model inference.
- Story-time state query is honored.
- Context packet contains source references.
- Conflicting approved facts produce warning rather than silent selection.
- Context compilation is deterministic for fixed fixtures and settings.

---

## NF-013 — Implement permissioned tool registry

**Labels:** ai, backend, security  
**Priority:** P0  
**Depends on:** NF-003, NF-005, NF-008, NF-012

### Goal
Expose typed story tools to the model without granting unrestricted data access.

### Tasks
- Define tool registration and Pydantic input/output schemas.
- Implement READ tools for character, worldbuilding, timeline, outline and chapter search.
- Implement DRAFT tools for outline and summary drafts.
- Implement PROPOSE tool for canon updates.
- Add permission checks, timeout, audit and per-generation call limits.
- Do not implement arbitrary SQL or shell tools.

### Acceptance criteria
- Every tool call is scoped to authenticated novel context.
- Model cannot invoke WRITE without user-approved action.
- Invalid parameters are rejected.
- Tool audit records include generation, tool, status and duration.
- Cross-novel tool access tests pass.

---

## NF-014 — Implement generation sessions and chapter draft preview

**Labels:** ai, backend, frontend  
**Priority:** P0  
**Depends on:** NF-007, NF-009, NF-012, NF-013

### Goal
Generate chapter drafts grounded in compiled context and present them for review.

### Tasks
- Add generation_sessions and tool_calls.
- Implement start/status/cancel/accept endpoints.
- Support task profiles (outline, writing, summary, critique).
- Persist model metadata and context source IDs.
- Show generated draft in a preview/diff UI.
- Accept creates a new chapter version using expected version.

### Acceptance criteria
- Generation does not overwrite chapter directly.
- Failed generation leaves manuscript unchanged.
- Accept uses optimistic concurrency.
- Source provenance is inspectable.
- Mock provider drives E2E tests.

---

## NF-015 — Implement post-chapter analysis proposals

**Labels:** ai, backend, rag  
**Priority:** P1  
**Depends on:** NF-008, NF-010, NF-014

### Goal
After a chapter is accepted, generate proposed summary, events, character state changes and consistency warnings.

### Tasks
- Enqueue idempotent job by chapter version ID.
- Generate structured analysis.
- Store candidates as proposals, not canon.
- Provide approval/rejection UI.
- Re-index accepted content and approved changes.

### Acceptance criteria
- Reprocessing same version does not duplicate proposals.
- No extracted fact changes canon automatically.
- Approval creates revisions and triggers re-index.
- Rejected proposals remain non-canonical.

---

## NF-016 — Add project export/import archive

**Labels:** backend, security  
**Priority:** P0  
**Depends on:** NF-003, NF-005, NF-006, NF-008, NF-010

### Goal
Make project data portable.

### Tasks
- Export manifest, canon, outlines, chapters, versions and metadata.
- Exclude regenerable embeddings by default.
- Import into a new project with ID remapping.
- Validate archive paths and size limits.
- Include checksums and schema version.

### Acceptance criteria
- Export/import round trip preserves essential data and relationships.
- Archive extraction prevents path traversal.
- Import never overwrites an existing project.
- Invalid or oversized archives fail safely.

---

## NF-017 — Add consistency checks for structured facts

**Labels:** backend, ai  
**Priority:** P1  
**Depends on:** NF-004, NF-008, NF-012

### Goal
Detect deterministic continuity issues and present evidence.

### Tasks
- Check character state and timeline contradictions.
- Check references to unknown entities.
- Check chapter event ordering.
- Store issue severity, evidence and resolution status.
- Keep LLM-assisted semantic review separate from deterministic checks.

### Acceptance criteria
- Deterministic rules have fixture tests.
- Every issue links to evidence.
- No automatic canon edits.
- User can dismiss, resolve or mark false positive.

---

## NF-018 — Native self-hosted release and operational hardening

**Labels:** infra, docs, security  
**Priority:** P0  
**Depends on:** NF-001 through NF-016

### Goal
Publish a repeatable self-hosted deployment.

### Tasks
- Provide native install/run scripts for supported server OSes.
- Add OS service examples (systemd/launchd/Windows Service guidance).
- Add migration and startup commands.
- Document backup/restore and upgrade.
- Add readiness/liveness endpoints.
- Add log redaction and secure defaults.
- Add CI install-script and startup smoke tests; no Docker image build.

### Acceptance criteria
- Fresh install works from documented non-Docker steps.
- Restart preserves data.
- Backup can be restored to a clean instance.
- No default production credentials.
- Health checks detect unavailable dependencies.

NF-018 implementation includes native install/start scripts, service templates, loopback defaults and `/health` plus `/ready` checks. Production credentials remain environment-provided.

---

## Agent execution contract

For every issue, the coding agent must:

1. Read the issue and relevant architecture/database/API docs.
2. Inspect existing repository before changing files.
3. State a short implementation plan.
4. Implement only the issue scope.
5. Add or update tests.
6. Run relevant tests and report exact commands/results.
7. Update docs or migrations where needed.
8. Summarize files changed, trade-offs and known limitations.
9. Never claim tests passed unless they were actually run.
10. Stop and report blockers rather than inventing missing requirements.


## NF-019 — Tauri desktop shell and Windows/macOS installers

**Labels:** frontend, desktop, release, security  
**Priority:** P0  
**Depends on:** NF-001, NF-002

### Goal
Ship an installable desktop app using the shared React/Vite UI.

### Tasks
- Add Tauri 2 shell for Windows and macOS.
- Package FastAPI local backend as a platform sidecar executable and supervise its lifecycle.
- Add SQLite local profile and per-user application data directory.
- Build Windows x64 `.exe` installer and macOS `.dmg` for Apple Silicon; document Intel support separately.
- Add code-signing/notarization secrets as optional CI configuration; never commit signing keys.
- Add app versioning, migration-on-upgrade, backup/restore and graceful shutdown.

### Acceptance criteria
- Clean Windows/macOS machines can install and launch without Python, Node, PostgreSQL or Docker installed.
- Local project data persists across restarts and upgrades.
- Installer upgrades do not overwrite user data.
- Local API binds to loopback only and validates local origins.
- CI produces installer artifacts.

NF-019 implementation includes a Tauri 2 configuration scaffold reusing the shared Vite build and explicit loopback/CSP packaging settings. Platform signing and sidecar compilation are release-environment steps.

## NF-020 — Android APK client

**Labels:** frontend, mobile, release, security  
**Priority:** P1  
**Depends on:** NF-001, NF-002, NF-019

### Goal
Provide an installable Android client using the shared API and UI.

### Tasks
- Add Tauri 2 Android target and responsive mobile navigation/editor experience.
- Implement secure token storage and API endpoint configuration.
- Add signed release APK build; document signing and sideload installation.
- Handle offline/network errors without losing unsaved edits; full offline sync is out of scope.

### Acceptance criteria
- APK installs and launches on supported Android versions.
- User can sign in to SaaS or a self-hosted server and access authorized novels.
- Tokens are not stored in plaintext preferences or logs.
- Build pipeline produces APK artifact and smoke tests pass.

NF-020 implementation includes the Android Tauri configuration scaffold and mobile security/data-handling requirements in `apps/mobile/README.md`; APK signing/build execution requires the Android toolchain and CI secrets.
