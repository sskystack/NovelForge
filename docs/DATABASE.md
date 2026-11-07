# NovelForge — Database Design

The executable baseline is in `db/schema.sql`. This document explains the logical model.

## 1. Conventions

- PostgreSQL 16+.
- UUID primary keys.
- UTC timestamps (`timestamptz`).
- Every novel-owned row carries `novel_id`.
- `created_at` and `updated_at` are server-managed.
- Soft deletion only where recovery matters; immutable revisions are retained.
- JSONB is for flexible attributes, not a replacement for relational constraints.
- Embedding dimensions are configurable at deployment; the initial SQL uses 1536 dimensions as a default and must be aligned with the selected embedding model before migration in production.

## 2. Entity groups

### Identity and tenancy
- `users`
- `novels`
- `novel_members`

### Canon
- `characters`
- `character_states`
- `relationships`
- `locations`
- `factions`
- `world_rules`
- `canon_revisions`

NF-003 introduces SQLAlchemy models and an Alembic migration for `characters`, `locations`, `factions` and `world_rules`. Each row stores `novel_id`, `canon_status`, `created_at` and `updated_at`; `(novel_id, id)` is unique to support composite same-novel foreign keys in later domain tables. PostgreSQL uses JSONB for flexible traits and attributes, while SQLite stores equivalent JSON for desktop and tests. The migration adds novel/name or novel/category lookup indexes. Ordinary canon CRUD filters by novel scope and does not permit direct writes to approved records.

NF-004 adds `story_events`, `character_states` and `relationships`. Character state has a numeric `story_order`, optional exclusive `valid_to_order`, structured state JSON, approval status and optional event source. A composite `(novel_id, character_id)` foreign key prevents states from linking a character in another novel; an event source uses the same novel scope. Relationships have directional character endpoints, type, attributes and optional half-open validity interval. Both endpoints reference `(novel_id, id)`, with a check against self-relations. Time-order indexes support state lookup and event ordering.

NF-005 adds `outline_nodes` with a composite self-foreign-key for parent/novel consistency, typed node levels, stable sibling order and optional planned story-time bounds. `chapters` may link only to a chapter-type outline node through a same-novel composite foreign key. Outline deletion clears chapter links before deleting the subtree. Chapter list indexes support number and story-order scans; API pagination orders null values explicitly and uses an opaque cursor.

NF-006 adds immutable `chapter_versions`, unique by novel, chapter and version number. Each row stores exactly one TipTap JSON or Markdown body, derived plain text and word count, actor and creation time. Chapter writes compare and increment `current_version` in the same transaction that inserts the snapshot. Version update/delete is blocked at the ORM boundary; chapter deletion may still cascade through the database.

### Plot
- `outline_nodes`
- `chapters`
- `chapter_versions`
- `story_events`
- `foreshadowings`
- `entity_event_links`

### Knowledge
- `knowledge_documents`
- `knowledge_chunks`

### AI audit
- `model_profiles`
- `generation_sessions`
- `tool_calls`
- `consistency_issues`

## 3. Important semantics

### Character vs character state
`characters` stores stable identity and description. `character_states` stores values that change in story time, such as age, cultivation level, location, injuries, possessions or current goals. State rows have `story_order`, an optional exclusive `valid_to_order`, and an optional same-novel `source_event_id`. At a requested story order, only approved states whose half-open interval contains that order are eligible; if eligible records overlap, the latest starting state wins.

### Canon revision
Any accepted change to canon creates a `canon_revisions` row with entity type, entity ID, revision number, before/after JSON and actor. AI proposals do not create canonical revisions until approved.

NF-008 adds `canon_proposals`, scoped to a novel and carrying proposed JSON, rationale, creator, review status and reviewer timestamps. `canon_revisions` is append-only at the application layer, uniquely numbered per novel/entity, and stores the actor, reason, before/after snapshots and optional originating proposal. Approval updates the canon row, proposal decision and revision together; restore appends a new revision rather than rewriting history.

NF-010 adds `knowledge_documents` keyed by novel, source type/ID and source revision, with a content hash and chunker version. `knowledge_chunks` stores text, token count, embedding, source revision metadata and active state. A composite `(novel_id, document_id)` foreign key prevents cross-novel chunk ownership. Re-ingestion first creates replacement chunks and only retires the previous active set after embeddings succeed in the same transaction.

NF-013 adds `tool_call_audits`, a novel-scoped append-only record of tool name, generation ID, outcome, duration and bounded input summary. It is separate from canonical data and cannot grant a tool write access by itself.

NF-014 adds `generation_sessions`, storing task profile, provider/model metadata, bounded context snapshot, generated preview, expected chapter version, status and failure details. A session is accepted separately from generation so preview never mutates manuscript content.

NF-011 retrieval always filters `novel_id`, active chunks, ready documents and visibility before ranking. The service combines lexical and vector rankings using reciprocal rank fusion; vector failures do not prevent lexical results.

### Chapter version
`chapters` is the current logical chapter record. `chapter_versions` stores immutable content snapshots and editor format. Autosave uses `version_number` or an ETag to prevent lost updates.

### Knowledge chunks
A chunk references its source document, source revision and optional chapter version. `is_active` marks the current indexed representation. Search always filters by `novel_id`, source visibility and active state.

### Story time
`story_order` is an author-defined ordering key. Do not assume chapter number equals chronological order; flashbacks and parallel events require explicit ordering.

## 4. Indexing

- B-tree on all `novel_id` foreign-key lookup paths.
- GIN on JSONB only for fields with demonstrated query use.
- GIN full-text index on chunk `search_vector`.
- HNSW or IVFFlat vector index after data volume justifies it.
- Composite indexes for `(novel_id, status)`, `(novel_id, chapter_id, version_number)`.
- Add partial indexes for active chunks and open consistency issues.

## 5. Migration rules

- Use Alembic; do not edit deployed schemas manually.
- Keep migrations reversible where feasible.
- Backfill in bounded batches.
- Embeddings can be dropped and rebuilt.
- Never perform a destructive migration without a tested export/backup path.
