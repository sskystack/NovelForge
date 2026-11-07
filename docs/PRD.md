# NovelForge — Product Requirements Document

**Version:** 1.0  
**Status:** Baseline for MVP  
**Product type:** Open-source, AI-assisted long-form fiction workspace  
**License target:** Apache-2.0

## 1. Product vision

NovelForge helps authors plan, write, maintain and revise long-form fiction without losing control of canon. It combines structured story data, versioned project files, chapter editing, hybrid retrieval and permissioned AI tools.

**Core promise:** AI writing grounded in the current, author-approved state of the novel—not merely the last chat transcript.

## 2. Target users

### Primary
- Long-form fiction writers working on multi-volume stories.
- Writers who use AI for brainstorming, outlining, drafting or editing.
- Authors who need consistent character, world and timeline records.

### Secondary
- Writing groups and editors (future collaboration features).
- Technical self-hosters who want local control of manuscripts and model providers.

## 3. Problems to solve

1. Story facts are scattered across notes, documents and chat histories.
2. Models forget or contradict established facts over long projects.
3. Characters change state over time; a single static profile is insufficient.
4. Outlines, chapters, events and foreshadowing are disconnected.
5. Authors cannot reliably inspect which sources informed a generated passage.
6. AI may silently rewrite or invent canon.
7. Users need ownership, portability and provider choice.

## 4. Product principles

- Canon is explicit, versioned and author-controlled.
- Story time and document time are distinct.
- Every novel is an isolated knowledge space.
- Retrieval results retain provenance and version identity.
- AI output is a draft until accepted.
- No destructive tool action without explicit authorization.
- Provider adapters isolate vendor-specific APIs.
- Self-hosted and SaaS deployments share the same domain model.

## 5. Primary user journeys

### J1 — Create a novel
1. User creates a project with title, language, genre and premise.
2. System creates a default project structure and empty canon sections.
3. User chooses a starting workflow: blank project, guided worldbuilding, or import.
4. User can export the project at any time.

**Acceptance:** A new project has a unique ID, owner, settings, default folders and isolated retrieval namespace.

### J2 — Build story canon
1. User creates characters, locations, factions, world rules and relationships.
2. User records static facts and time-dependent character states separately.
3. User can mark a record as draft, proposed or canon.
4. Changes create immutable revisions.

**Acceptance:** A canon edit produces a revision record; prior versions remain inspectable and restorable.

### J3 — Plan plot
1. User creates a book-level outline.
2. User creates volumes and nested outline nodes.
3. User links nodes to characters, places, events and foreshadowing threads.
4. User reorders nodes and records planned chapter ranges.

**Acceptance:** Outline hierarchy is persisted and can be exported/imported without losing parent-child relations.

### J4 — Write a chapter
1. User opens a chapter in rich-text or Markdown mode.
2. User selects a writing action: continue, rewrite selection, draft from outline, brainstorm, critique.
3. System compiles relevant canon, recent narrative memory, chapter outline and user instructions.
4. Model generates a draft with source references and warnings.
5. User accepts, edits or rejects the result.
6. Accepted content is saved as a new chapter version.

**Acceptance:** Generation never overwrites a chapter without user action; every generation stores model/provider metadata and context provenance.

### J5 — Update story memory
1. After a chapter is saved, the system proposes a summary, story events, character state changes and possible canon conflicts.
2. User reviews proposed updates.
3. User accepts selected updates.
4. Accepted facts become structured story records and trigger re-indexing.

**Acceptance:** AI-extracted facts are not canon until approved; rejected proposals remain auditable but do not affect canonical retrieval.

### J6 — Search story knowledge
1. User or AI asks a question about a character, event, place or prior chapter.
2. System filters by novel and permission.
3. Hybrid retrieval returns structured facts and relevant text chunks.
4. UI shows source and version provenance.

**Acceptance:** Search results never cross novel boundaries and expose source chapter/document identifiers.

## 6. Functional requirements

Priority: P0 = MVP blocker, P1 = post-MVP, P2 = later.

### Project management
- P0: Create, list, update and archive novels.
- P0: Per-novel language, genre, premise and writing preferences.
- P0: Novel-scoped authorization on every query.
- P0: Export/import a complete project archive.
- P1: Project templates and shared workspaces.

### Canon and worldbuilding
- P0: Character CRUD with identity, traits, goals, background and constraints.
- P0: Character state snapshots with effective story time.
- P0: World rules, locations and factions.
- P0: Character relationships with type, directionality and validity interval.
- P0: Canon status: draft, proposed, canon, deprecated.
- P0: Revision history and restore.
- P1: Visual relationship graph.
- P1: Item, species, culture and magic-system specialized entities.

### Plot and narrative
- P0: Nested outline nodes for book, volume, arc and chapter.
- P0: Chapter CRUD, ordering and status.
- P0: Story events with story-time metadata.
- P0: Foreshadowing records with status and planned resolution.
- P0: Chapter summaries and narrative-memory chunks.
- P1: Drag-and-drop timeline and plot board.
- P1: Advanced arc and pacing analysis.

### Editor
- P0: TipTap rich-text mode.
- P0: Markdown source mode.
- P0: Autosave with optimistic concurrency (`version` / ETag).
- P0: Manual save and version history.
- P0: Selection-based rewrite and critique.
- P0: No silent overwrite; generated content is previewed first.
- P1: Offline editing and real-time collaboration.

### AI and model providers
- P0: Provider interface for chat/completion and embeddings.
- P0: User-configurable model profiles by task.
- P0: Timeouts, retries with bounded policy, token/cost metadata where provider exposes it.
- P0: Structured output validation.
- P0: Tool registry with permission tiers.
- P0: Generation session and tool-call audit log.
- P1: Reranker provider and model evaluation UI.
- P1: Agent workflow templates.

### RAG and context
- P0: Ingestion of canon records, chapters, summaries and uploaded text/Markdown.
- P0: Chunk metadata includes novel_id, source type, source ID, revision and story-time range.
- P0: PostgreSQL full-text + pgvector hybrid retrieval.
- P0: Hard novel and user access filters before ranking.
- P0: Canon facts outrank AI inferences and unapproved drafts.
- P0: Context budget and source citation output.
- P0: Re-index on approved revision; invalidate stale chunks.
- P1: Query rewriting, reranking and graph expansion.

### Consistency
- P0: Deterministic checks for explicit structured facts (age, location, ability, timeline).
- P0: AI-assisted review returns evidence and severity, not unsupported certainty.
- P0: Conflicts are proposals; never auto-edit canon.
- P1: Cross-chapter semantic contradiction detection.
- P1: Continuity dashboard.

### Deployment and operations
- P0: Self-hosted deployment using native installation scripts; Docker is not required.
- P0: Environment-variable based configuration.
- P0: Health/readiness endpoints.
- P0: Database migrations and backup/restore documentation.
- P0: Structured logs and request IDs.
- P1: SaaS tenant quotas, billing and admin console.

## 7. Non-functional requirements

- Security: enforce user and novel authorization at service/repository boundaries.
- Privacy: do not train on user content; provider data handling must be disclosed and configurable.
- Reliability: generation failure must not corrupt chapter content.
- Data integrity: optimistic concurrency for chapter edits; transactional canon revisions.
- Portability: project archive export must include source documents and metadata, excluding regenerable embeddings by default.
- Performance: target p95 under 500 ms for ordinary CRUD endpoints under a small single-instance workload; retrieval target p95 under 2 s for a modest project corpus (hardware/model dependent).
- Accessibility: keyboard navigable editor controls and semantic UI.
- Observability: trace generation, retrieval and tool calls with correlation IDs.
- Localization: UI and novel content language are independent; MVP UI may start in English/Chinese.

## 8. MVP scope and release gates

### v0.1 must include
- Project, canon, outline, chapter and foreshadowing basics.
- Rich text + Markdown.
- Provider abstraction.
- Hybrid RAG and Context Compiler.
- Permissioned tools.
- Proposed canon updates and approval.
- Chapter generation preview and versioning.
- Export/import.
- Native self-hosted install/run scripts (no Docker dependency).
- Windows `.exe`, macOS `.dmg`, Android `.apk` release artifacts.
- Unit, integration and end-to-end tests.

### Release blockers
- Any cross-novel data leakage.
- Any unapproved canon mutation.
- Chapter content lost during generation or autosave.
- Export cannot round-trip essential project data.
- Tool can execute arbitrary SQL or host shell.
- Secret/API key exposure in logs or browser bundle.

## 9. Success metrics

Product:
- Time to create a usable project.
- Percentage of AI drafts accepted or partially accepted.
- Weekly active projects.
- Chapter retention / return rate.
- Export success rate.
- User-reported continuity issue rate.

Engineering:
- Retrieval precision@k on curated test questions.
- Canon fact accuracy.
- Cross-novel leakage tests: zero.
- Unapproved canon writes: zero.
- Chapter save conflict detection rate.
- Generation failure recovery rate.

## 10. Explicit exclusions for v0.1

- Autonomous end-to-end novel writing without review.
- Public content hosting or publishing marketplace.
- Payment and subscription billing.
- Real-time multi-cursor editing.
- Training custom foundation models.
- Unrestricted computer-use or shell tools.
