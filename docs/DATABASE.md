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
`characters` stores stable identity and description. `character_states` stores values that change in story time, such as age, cultivation level, location, injuries, possessions or current goals. State rows have `valid_from_event_id` / `valid_to_event_id` and an optional `story_order`.

### Canon revision
Any accepted change to canon creates a `canon_revisions` row with entity type, entity ID, revision number, before/after JSON and actor. AI proposals do not create canonical revisions until approved.

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
