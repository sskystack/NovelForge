-- NovelForge initial PostgreSQL schema
-- Requires PostgreSQL 16+ and pgvector.
-- Production deployments should use Alembic migrations generated from equivalent models.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE novel_status AS ENUM ('active', 'archived');
CREATE TYPE canon_status AS ENUM ('draft', 'proposed', 'canon', 'deprecated');
CREATE TYPE chapter_status AS ENUM ('planned', 'draft', 'in_progress', 'review', 'completed');
CREATE TYPE content_format AS ENUM ('tiptap', 'markdown');
CREATE TYPE proposal_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE generation_status AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE foreshadowing_status AS ENUM ('open', 'hinted', 'resolved', 'abandoned');

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  display_name text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE auth_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash char(64) NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_auth_sessions_user_expires ON auth_sessions(user_id, expires_at);

CREATE TABLE novels (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  title text NOT NULL,
  language text NOT NULL DEFAULT 'zh-CN',
  genre jsonb NOT NULL DEFAULT '[]'::jsonb,
  premise text NOT NULL DEFAULT '',
  writing_preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
  status novel_status NOT NULL DEFAULT 'active',
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  archived_at timestamptz
);
CREATE INDEX ix_novels_owner_status ON novels(owner_user_id, status);

CREATE TABLE novel_members (
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner','editor','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (novel_id, user_id)
);
CREATE INDEX ix_novel_members_user ON novel_members(user_id);

CREATE TABLE locations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text NOT NULL DEFAULT '',
  canon_status canon_status NOT NULL DEFAULT 'draft',
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id)
);
CREATE INDEX ix_locations_novel_name ON locations(novel_id, name);

CREATE TABLE factions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text NOT NULL DEFAULT '',
  canon_status canon_status NOT NULL DEFAULT 'draft',
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id)
);
CREATE INDEX ix_factions_novel_name ON factions(novel_id, name);

CREATE TABLE characters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  name text NOT NULL,
  aliases jsonb NOT NULL DEFAULT '[]'::jsonb,
  summary text NOT NULL DEFAULT '',
  personality jsonb NOT NULL DEFAULT '{}'::jsonb,
  background text NOT NULL DEFAULT '',
  goals jsonb NOT NULL DEFAULT '[]'::jsonb,
  constraints jsonb NOT NULL DEFAULT '[]'::jsonb,
  canon_status canon_status NOT NULL DEFAULT 'draft',
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id)
);
CREATE INDEX ix_characters_novel_name ON characters(novel_id, name);
CREATE INDEX ix_characters_attributes ON characters USING gin(attributes);

CREATE TABLE world_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  title text NOT NULL,
  category text NOT NULL DEFAULT 'general',
  description text NOT NULL,
  constraints jsonb NOT NULL DEFAULT '{}'::jsonb,
  canon_status canon_status NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id)
);
CREATE INDEX ix_world_rules_novel_category ON world_rules(novel_id, category);

CREATE TABLE story_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  story_order numeric(20,6) NOT NULL,
  story_time_label text,
  event_type text NOT NULL DEFAULT 'general',
  canon_status canon_status NOT NULL DEFAULT 'draft',
  source_chapter_id uuid,
  occurred_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id)
);
CREATE INDEX ix_story_events_order ON story_events(novel_id, story_order);

CREATE TABLE character_states (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  character_id uuid NOT NULL,
  story_order numeric(20,6) NOT NULL,
  valid_to_order numeric(20,6),
  state jsonb NOT NULL,
  source_event_id uuid,
  canon_status canon_status NOT NULL DEFAULT 'proposed',
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to_order IS NULL OR valid_to_order > story_order),
  UNIQUE (novel_id, id),
  FOREIGN KEY (novel_id, character_id) REFERENCES characters(novel_id, id) ON DELETE CASCADE,
  FOREIGN KEY (novel_id, source_event_id) REFERENCES story_events(novel_id, id) ON DELETE SET NULL (source_event_id)
);
CREATE INDEX ix_character_states_lookup ON character_states(novel_id, character_id, story_order DESC);

CREATE TABLE relationships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  from_character_id uuid NOT NULL,
  to_character_id uuid NOT NULL,
  relationship_type text NOT NULL,
  description text NOT NULL DEFAULT '',
  valid_from_order numeric(20,6),
  valid_to_order numeric(20,6),
  canon_status canon_status NOT NULL DEFAULT 'draft',
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (from_character_id <> to_character_id),
  CHECK (valid_to_order IS NULL OR valid_from_order IS NULL OR valid_to_order > valid_from_order),
  FOREIGN KEY (novel_id, from_character_id) REFERENCES characters(novel_id, id) ON DELETE CASCADE,
  FOREIGN KEY (novel_id, to_character_id) REFERENCES characters(novel_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_relationships_from ON relationships(novel_id, from_character_id);
CREATE INDEX ix_relationships_to ON relationships(novel_id, to_character_id);

CREATE TABLE outline_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  parent_id uuid,
  node_type text NOT NULL CHECK (node_type IN ('book','volume','arc','chapter','scene','beat')),
  title text NOT NULL,
  synopsis text NOT NULL DEFAULT '',
  sort_order integer NOT NULL DEFAULT 0,
  planned_start_order numeric(20,6),
  planned_end_order numeric(20,6),
  status text NOT NULL DEFAULT 'planned',
  linked_entity_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id),
  FOREIGN KEY (novel_id, parent_id) REFERENCES outline_nodes(novel_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_outline_parent_order ON outline_nodes(novel_id, parent_id, sort_order);

CREATE TABLE chapters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  outline_node_id uuid,
  title text NOT NULL,
  chapter_number integer,
  story_order numeric(20,6),
  status chapter_status NOT NULL DEFAULT 'planned',
  current_version integer NOT NULL DEFAULT 0,
  summary text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id),
  FOREIGN KEY (novel_id, outline_node_id) REFERENCES outline_nodes(novel_id, id) ON DELETE SET NULL (outline_node_id)
);
CREATE INDEX ix_chapters_order ON chapters(novel_id, chapter_number);
CREATE INDEX ix_chapters_story_order ON chapters(novel_id, story_order);

CREATE TABLE chapter_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  chapter_id uuid NOT NULL,
  version_number integer NOT NULL,
  content_format content_format NOT NULL,
  tiptap_json jsonb,
  markdown text,
  plain_text text NOT NULL DEFAULT '',
  word_count integer NOT NULL DEFAULT 0,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  source_generation_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id),
  UNIQUE (chapter_id, version_number),
  FOREIGN KEY (novel_id, chapter_id) REFERENCES chapters(novel_id, id) ON DELETE CASCADE,
  CHECK (
    (content_format = 'tiptap' AND tiptap_json IS NOT NULL) OR
    (content_format = 'markdown' AND markdown IS NOT NULL)
  )
);
CREATE INDEX ix_chapter_versions_history ON chapter_versions(novel_id, chapter_id, version_number DESC);

CREATE TABLE foreshadowings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  created_chapter_id uuid,
  planned_resolution_chapter_id uuid,
  status foreshadowing_status NOT NULL DEFAULT 'open',
  importance text NOT NULL DEFAULT 'medium',
  notes text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id),
  FOREIGN KEY (novel_id, created_chapter_id) REFERENCES chapters(novel_id, id) ON DELETE SET NULL (created_chapter_id),
  FOREIGN KEY (novel_id, planned_resolution_chapter_id) REFERENCES chapters(novel_id, id) ON DELETE SET NULL (planned_resolution_chapter_id)
);
CREATE INDEX ix_foreshadowings_status ON foreshadowings(novel_id, status);

CREATE TABLE entity_event_links (
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  event_id uuid NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  relation text NOT NULL DEFAULT 'involved',
  PRIMARY KEY (event_id, entity_type, entity_id),
  FOREIGN KEY (novel_id, event_id) REFERENCES story_events(novel_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_entity_event_entity ON entity_event_links(novel_id, entity_type, entity_id);

CREATE TABLE canon_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  revision_number integer NOT NULL,
  before_data jsonb,
  after_data jsonb NOT NULL,
  change_reason text NOT NULL DEFAULT '',
  actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  source_proposal_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, entity_type, entity_id, revision_number)
);
CREATE INDEX ix_canon_revisions_entity ON canon_revisions(novel_id, entity_type, entity_id, revision_number DESC);

CREATE TABLE knowledge_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  source_type text NOT NULL,
  source_id uuid,
  title text NOT NULL,
  source_revision integer NOT NULL DEFAULT 1,
  visibility text NOT NULL DEFAULT 'approved' CHECK (visibility IN ('approved','draft','private')),
  content_hash text NOT NULL,
  chunker_version text NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id),
  UNIQUE (novel_id, source_type, source_id, source_revision)
);
CREATE INDEX ix_knowledge_docs_source ON knowledge_documents(novel_id, source_type, source_id);

-- Default vector size is 1536. Change this dimension to match the configured embedding model.
CREATE TABLE knowledge_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  document_id uuid NOT NULL,
  chunk_index integer NOT NULL,
  content text NOT NULL,
  token_count integer NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding vector(1536),
  search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (novel_id, document_id) REFERENCES knowledge_documents(novel_id, id) ON DELETE CASCADE,
  UNIQUE (document_id, chunk_index)
);
CREATE INDEX ix_knowledge_chunks_novel_active ON knowledge_chunks(novel_id, is_active);
CREATE INDEX ix_knowledge_chunks_fts ON knowledge_chunks USING gin(search_vector);
-- Create vector index after initial data volume and confirm pgvector version supports chosen index method:
-- CREATE INDEX ix_knowledge_chunks_embedding ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE model_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  task_type text NOT NULL,
  provider text NOT NULL,
  model_name text NOT NULL,
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  secret_reference text,
  is_default boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id)
);
CREATE INDEX ix_model_profiles_task ON model_profiles(novel_id, task_type);

CREATE TABLE generation_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  chapter_id uuid,
  task_type text NOT NULL,
  status generation_status NOT NULL DEFAULT 'queued',
  provider text,
  model_name text,
  instructions text NOT NULL DEFAULT '',
  context_manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
  output_payload jsonb,
  error_code text,
  error_message_safe text,
  input_tokens integer,
  output_tokens integer,
  estimated_cost numeric(14,6),
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id),
  FOREIGN KEY (novel_id, chapter_id) REFERENCES chapters(novel_id, id) ON DELETE SET NULL (chapter_id)
);
CREATE INDEX ix_generation_sessions_status ON generation_sessions(novel_id, status, created_at DESC);

CREATE TABLE tool_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  generation_id uuid NOT NULL,
  tool_name text NOT NULL,
  permission_tier text NOT NULL CHECK (permission_tier IN ('read','draft','propose','write')),
  input_redacted jsonb NOT NULL DEFAULT '{}'::jsonb,
  output_summary jsonb,
  status text NOT NULL,
  duration_ms integer,
  approval_reference uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (novel_id, generation_id) REFERENCES generation_sessions(novel_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_tool_calls_generation ON tool_calls(novel_id, generation_id, created_at);

CREATE TABLE canon_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  entity_type text NOT NULL,
  entity_id uuid,
  proposed_data jsonb NOT NULL,
  rationale text NOT NULL DEFAULT '',
  source_generation_id uuid,
  status proposal_status NOT NULL DEFAULT 'pending',
  reviewed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (novel_id, id),
  FOREIGN KEY (novel_id, source_generation_id) REFERENCES generation_sessions(novel_id, id) ON DELETE SET NULL
);
CREATE INDEX ix_canon_proposals_status ON canon_proposals(novel_id, status, created_at DESC);

CREATE TABLE consistency_issues (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
  issue_type text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('info','low','medium','high','critical')),
  title text NOT NULL,
  explanation text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  confidence numeric(4,3),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','dismissed','false_positive')),
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);
CREATE INDEX ix_consistency_open ON consistency_issues(novel_id, status, severity);

-- Notes:
-- 1. Use Alembic migrations in application development; this SQL is a baseline.
-- 2. Add updated_at triggers or manage timestamps in the application consistently.
-- 3. For SaaS, add and test PostgreSQL RLS policies as defense in depth.
-- 4. Validate pgvector dimension against the selected embedding model before deployment.
