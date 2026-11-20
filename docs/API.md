# NovelForge — API Specification

Base path: `/api/v1`
Format: JSON, UTF-8
Authentication uses an opaque local session in an `HttpOnly`, `SameSite=Strict` cookie, or the revocable session token returned by login in `X-NovelForge-Session` as `Authorization: Bearer ...`. The desktop profile remains local-first and does not depend on remote authentication.
The desktop sidecar also requires its per-launch `X-NovelForge-Local-Token` on every non-OPTIONS request, including health probes. All domain resources are scoped to the authenticated owner and novel. This token is independent of the author login session.

Browser mutations authenticated by cookies require `X-CSRF-Token`, matching the readable `novelforge_csrf` cookie. The session cookie is named `novelforge_session`, contains a random token, and is backed by a database row containing only its SHA-256 hash. Set `SESSION_COOKIE_SECURE=true` whenever the API is served over HTTPS. Auth endpoints and validation failures use `application/problem+json` with a request ID.

## 1. Common conventions

- IDs are UUID strings.
- Timestamps are ISO 8601 UTC.
- Chapter pagination uses `limit` (default 20, max 100) and opaque `cursor`; other collections document their own bounded array response.
- Errors use `application/problem+json`.
- Mutating chapter endpoints require `If-Match` or `expected_version`.
- Model tools never accept raw SQL or shell commands. Explicit author-owned MCP registration is the separate trusted-executable configuration boundary documented below.

### Error shape

```json
{
  "type": "https://novelforge.dev/problems/version-conflict",
  "title": "Version conflict",
  "status": 409,
  "detail": "The chapter has changed since it was loaded.",
  "code": "CHAPTER_VERSION_CONFLICT",
  "request_id": "..."
}
```

## 2. Endpoint groups

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout` (requires `X-CSRF-Token` while logged in)
- `GET /auth/me`

### Novels
- `GET /novels`
- `POST /novels`
- `GET /novels/{novel_id}`
- `PATCH /novels/{novel_id}`
- `DELETE /novels/{novel_id}` (archive, not hard delete)
- `GET /novels/{novel_id}/export`
- `POST /novels/import`

Novel endpoints require an authenticated local owner profile. Requests for another profile's novel return `404`. The list hides archived novels by default; `GET /novels?include_archived=true` includes the current profile's archived projects. `PATCH /novels/{novel_id}` with `{"status":"active"}` restores an archived novel. Create, update and archive requests require the CSRF header.

Registration accepts `email`, `password` (12-128 characters) and optional `display_name`; email is normalized to lowercase. Registration does not create a login session. Login returns the current user and sets the session and CSRF cookies. Logout revokes the database session and clears both cookies.

### Canon
- `GET|POST /novels/{novel_id}/characters`
- `GET|PATCH|DELETE /novels/{novel_id}/characters/{character_id}`
- `GET|POST /novels/{novel_id}/characters/{character_id}/states`
- `GET|POST /novels/{novel_id}/relationships`
- `GET|POST /novels/{novel_id}/locations`
- `GET|POST /novels/{novel_id}/factions`
- `GET|POST /novels/{novel_id}/world-rules`
- `GET /novels/{novel_id}/canon/revisions`
- `GET|POST /novels/{novel_id}/canon/proposals`
- `POST /novels/{novel_id}/canon/proposals/{proposal_id}/approve`
- `POST /novels/{novel_id}/canon/proposals/{proposal_id}/reject`
- `POST /novels/{novel_id}/canon/revisions/restore`

NF-003 provides full CRUD for characters, locations, factions and world rules under `/api/v1/novels/{novel_id}/...`. All requests require an authenticated owner; every child lookup includes both `novel_id` and entity ID, returning `404` for records outside the path novel. Collection reads return approved `canon` records by default. Authors may pass `include_non_canon=true` to inspect drafts and proposals. New records default to `draft`; direct creation or promotion to `canon` is rejected until the approval/revision workflow is implemented. Approved records cannot be edited or deleted through ordinary CRUD. Create, update and delete require the CSRF header.

Character records contain stable identity fields (`name`, `aliases`, `summary`, `personality`, `background`, `goals`, `constraints`, `attributes`). Locations and factions contain `name`, `description` and `attributes`. World rules contain `title`, `category`, `description` and structured `constraints`.

NF-004 adds `POST|GET /novels/{novel_id}/events`, `POST|GET /novels/{novel_id}/characters/{character_id}/states`, `GET /novels/{novel_id}/characters/{character_id}/state-at?story_order=N`, `GET /novels/{novel_id}/character-states?story_order=N`, and `POST|GET /novels/{novel_id}/relationships`. Character-state and relationship intervals are half-open: `valid_from_order` / `story_order` is included and `valid_to_order` is excluded. A state-at query returns the latest approved state applicable at that story order; it returns `state: null` when no approved state applies. Relationship reads show approved records by default, with `include_non_canon=true` available for review. Event references and both relationship endpoints must belong to the path novel.

NF-008 proposals accept an `entity_type`, optional `entity_id`, validated `proposed_data` and rationale. Creation, approval, rejection and restore require CSRF protection and the novel owner session. Proposal payloads never write canonical records. Approval applies the change and appends an immutable revision in one transaction; rejection only records the decision. `GET /canon/revisions` can be filtered by `entity_type` and `entity_id`. Restore copies the selected revision's after-state into the entity and appends another revision, preserving the audit trail. Stable canon entities support create and update proposals; story events, character states and relationships support create proposals.

### Planning and chapters
- `GET|POST /novels/{novel_id}/outlines`
- `PATCH|DELETE /novels/{novel_id}/outlines/{node_id}`
- `POST /novels/{novel_id}/outlines/reorder`
- `GET|POST /novels/{novel_id}/chapters`
- `GET|PATCH|DELETE /novels/{novel_id}/chapters/{chapter_id}`
- `GET /novels/{novel_id}/chapters/{chapter_id}/versions`
- `POST /novels/{novel_id}/chapters/{chapter_id}/restore/{version_id}`
- `GET|POST /novels/{novel_id}/events`

Foreshadowing CRUD remains a design target, not an implemented route.

NF-005 persists nested outline nodes and chapter planning metadata. `GET /outlines` returns a recursively nested tree; children use deterministic `sort_order`, title and ID ordering. `POST /outlines/reorder` accepts a parent and the complete sibling ID order, requiring every sibling exactly once. Parent changes reject cycles and cross-novel references. Deleting an outline node deletes its subtree and clears linked chapter outline IDs. Only `chapter` outline nodes can be assigned to chapter rows. Chapter lists accept `limit` (1-100) and an opaque `cursor`; ordering is deterministic by number, story order and ID.

NF-006 creates an empty TipTap version 1 when a chapter is created. `GET /chapters/{chapter_id}` and every successful write return `ETag: "N"`. `PATCH` requires a matching `If-Match` header and appends an immutable version; a stale tag returns `409 CHAPTER_VERSION_CONFLICT`. A content update requires `content_format` and either TipTap `content` JSON or `markdown`; metadata-only patches retain the current content and still append a snapshot. Version history is returned newest first. Restore also requires the current `If-Match`, copies a selected historical body into a new version, and never changes the source version.

### Knowledge and consistency
- `GET /novels/{novel_id}/knowledge/search`
- `GET|POST /novels/{novel_id}/knowledge/documents`
- `DELETE /novels/{novel_id}/knowledge/documents/{document_id}`
- `POST /novels/{novel_id}/consistency/check`
- `GET /novels/{novel_id}/consistency/issues`
- `POST /novels/{novel_id}/consistency/issues/{issue_id}/resolve`

### AI
- `POST /novels/{novel_id}/ai/generations`
- `GET /novels/{novel_id}/ai/generations/{generation_id}`
- `POST /novels/{novel_id}/ai/generations/{generation_id}/cancel`
- `POST /novels/{novel_id}/ai/generations/{generation_id}/accept`

Task-specific model-profile CRUD remains deferred. Author model configuration uses `/settings/ai` below.

## 3. Key request/response examples

### Create novel

`POST /api/v1/novels`

```json
{
  "title": "星海纪元",
  "language": "zh-CN",
  "genre": ["仙侠", "成长"],
  "premise": "一个外门弟子逐步揭开古老星海秘密。",
  "writing_preferences": {
    "pov": "third_person_limited",
    "tense": "past",
    "style_notes": []
  }
}
```

Response `201`:

```json
{
  "id": "uuid",
  "title": "星海纪元",
  "language": "zh-CN",
  "status": "active",
  "created_at": "2026-01-01T00:00:00Z"
}
```

### Save chapter content

`PATCH /api/v1/novels/{novel_id}/chapters/{chapter_id}`

Headers: `If-Match: "7"`

```json
{
  "title": "第二十章：禁地",
  "content_format": "tiptap",
  "content": {"type": "doc", "content": []},
  "markdown": null
}
```

A successful response returns new version `8` and `ETag: "8"`. Stale updates return `409`.

### Search knowledge

`GET /api/v1/novels/{novel_id}/knowledge/search?query=林渊&limit=10`

Response:

```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "source_type": "chapter_version",
      "source_id": "uuid",
      "title": "第十二章：石碑",
      "source_revision": 3,
      "content": "...",
      "score": 0.032
    }
  ]
}
```

### Start generation

`POST /api/v1/novels/{novel_id}/ai/generations`

```json
{
  "task_profile": "writing",
  "chapter_id": "uuid",
  "instructions": "描写主角进入禁地后的探索，保持谨慎内敛的性格。",
  "token_budget": 4000
}
```

Response `202`:

```json
{
  "id": "uuid",
  "status": "succeeded",
  "output": {"content_format": "markdown", "markdown": "Draft text", "source_ids": [], "usage": {}}
}
```

## 4. API security rules

- Verify membership before resolving any novel-scoped resource.
- Verify child resource belongs to the path's novel.
- Apply authorization to tool calls, not only HTTP routes.
- Rate-limit generation and ingestion.
- Redact secrets and manuscript content from routine logs.
- Validate all provider output against schemas.
- Use CSRF protection for cookie-authenticated browser mutations.
- Limit upload size, MIME types and archive extraction paths.

NF-009 provider integration is backend-only. `mock` is the default deterministic provider for local development and CI. Configure an OpenAI-compatible server with `AI_PROVIDER=openai-compatible`, `AI_BASE_URL`, `AI_API_KEY` and optional `AI_TIMEOUT_SECONDS`; credentials are read by the API process and are never sent to browser code. The normalized contract covers chat responses, structured output, streaming events, tool calls, usage metadata and embeddings.

Knowledge ingestion now exposes `/knowledge/documents` (see section 7). Search is restricted to the authenticated novel, active chunks and ready documents; approved sources are default and drafts require `include_drafts=true`. Each result retains chunk/document IDs, source type/ID/revision, title, content and RRF score. Optional local FTS5 trigram/BM25, deterministic lexical and exact compatible-vector cosine rankings are fused. Missing FTS/embedding failures fall back to lexical scoring. Superseded chapter versions are excluded from current retrieval.

NF-013 exposes `GET /novels/{novel_id}/ai/tools` and `POST /novels/{novel_id}/ai/tools/{tool_name}/execute`. Inputs use strict Pydantic validation; every call checks owner and novel. This direct author API retains its per-registry cap and explicit approved_action contract. The model-driven Agent API instead uses persistent run budgets and exact step decisions. Draft tools return previews without persistence; propose_canon creates only a pending proposal. Audit rows contain size-limited local input summaries, not a universal secret-redaction guarantee. No SQL or shell tool is registered.

NF-014 exposes `POST /novels/{novel_id}/ai/generations`, `GET /novels/{novel_id}/ai/generations/{generation_id}`, `POST .../{generation_id}/cancel` and `POST .../{generation_id}/accept`. Generation responses contain a context snapshot and source IDs for inspection. Mock generation produces a persisted preview with `succeeded` status but does not change the chapter. Accept requires the expected chapter version and creates a normal immutable chapter version; stale acceptance returns the existing chapter conflict and leaves the manuscript unchanged.

The legacy generation and analysis routes execute synchronously despite returning HTTP 202. They are not background jobs. Use the new Agent run endpoints for asynchronous multi-turn execution and cancellation during provider waits.

NF-015 exposes `POST /novels/{novel_id}/ai/analysis/{chapter_version_id}` and `GET` for idempotent post-chapter analysis, plus `GET /novels/{novel_id}/ai/analysis-proposals` and approve/reject actions. Analysis is keyed by immutable chapter version. Structured candidates retain chapter/version evidence and remain pending until review. Approval delegates to the canon approval workflow and creates a canon revision; rejection does not modify canon.

NF-016 provides `GET /novels/{novel_id}/export` and binary `POST /novels/import`. Archives contain a schema-versioned manifest with checksums and JSON records for project data. Regenerable embeddings are omitted. Import validates ZIP paths, compressed and expanded size, entry count and checksums, creates a new active project, remaps IDs and never overwrites the source project.

NF-017 provides `POST /novels/{novel_id}/consistency/check`, filtered issue listing, and `POST /novels/{novel_id}/consistency/issues/{issue_id}/resolve`. Checks are deterministic and evidence-backed; they never edit canon. Issue resolution accepts `resolved`, `dismissed`, or `false_positive`.

NF-012 exposes `GET /novels/{novel_id}/context/compile?chapter_id=...`. The deterministic context packet separates canon facts, story-time state, events, chapter/outline material and retrieved prose. Every section includes a source reference and provenance; `token_budget` bounds the packet and `story_order` controls state/event selection. The compiler reports omissions as warnings and leaves model inference empty until a generation service fills it.

## 5. Asynchronous Agent runs (0.2.0)

`POST /novels/{novel_id}/agent/runs` returns 202 with a persisted queued run immediately:

```json
{"prompt":"检查人物和大纲","max_rounds":6,"max_tool_calls":12,"max_seconds":60,"max_tokens":12000,"use_mcp":false}
```

Limits: prompt 1–20,000 characters (nonblank), rounds 1–20, tool calls 1–40, active time 0.1–300 seconds, estimated aggregate tokens 100–100,000. All limits are optional and default to the example. At most four runs execute concurrently per sidecar.

- `GET /novels/{novel_id}/agent/runs` returns a newest-first array, at most 100 runs.
- `GET /novels/{novel_id}/agent/runs/{run_id}` returns one detailed run.
- `POST .../{run_id}/cancel` returns the detailed run; repeated cancellation is harmless.
- `POST .../{run_id}/steps/{step_id}/decision` accepts only `{"approve":true}` or false and returns 202. A duplicate/obsolete/changed target returns 409. Arguments cannot be replaced in the decision request.

Run fields: id, novel_id, prompt, status, provider, is_mock, model, output (string), error (nullable string), sources (array), tokens_used, tools_used, rounds_used, elapsed_seconds, created_at, updated_at, public limits, and steps. Step fields: id, sequence, kind (`model`/`tool`), status, nullable tool_name/tool_call_id, arguments, arguments_hash, result (JSON object), nullable error/decision, created_at. Source fields match knowledge search results above. Internal credentials, routing snapshots and configuration fingerprints are not returned.

Run status is queued/running/waiting_approval/succeeded/failed/cancelled/interrupted. Tool step statuses additionally include pending/rejected. An author decision approves the exact tool call; approving propose_canon only creates a pending canon proposal. Canon adoption and manuscript acceptance retain their existing separate author workflows.

Waiting approvals survive restart. Active runs found after restart become interrupted and are never automatically replayed; there is no generic resume/retry endpoint. Cancelling stops the wait and subsequent execution, but cannot physically recall an already sent HTTP request. Token budgets use an estimate plus reported usage; the adapter also sends max_tokens, but this is not a vendor billing guarantee.

## 6. Author-scoped model and MCP settings

`GET /settings/ai` returns a masked object:

```json
{"provider":"mock","base_url":"","chat_model":"mock-chat","embedding_model":"mock-embedding","timeout_seconds":30,"api_key_configured":false}
```

`PATCH /settings/ai` accepts any subset of provider (mock/openai-compatible), base_url, chat_model, embedding_model, timeout_seconds (1–120), and write-only api_key. An omitted key is preserved; empty string clears it. Returns the masked GET shape. HTTP model URLs must be loopback; other endpoints require HTTPS and cannot contain URL credentials/query/fragment. Local compatible servers may omit an API key.

`POST /settings/ai/test` returns `{ok,provider,model,message}` after a fixed benign prompt, without manuscript data; failures are generic 502 errors without credentials. Settings affect agent, generation, analysis, context and retrieval. Changing model configuration while a run waits invalidates that run instead of silently switching its provider.

MCP routes: `GET|POST /mcp/servers`, `GET|PATCH|DELETE /mcp/servers/{id}`, `POST /mcp/servers/{id}/test`. Collection GET is an array. POST returns 201 server; PATCH accepts any subset of configuration fields and validates the merged configuration, preserving omitted secrets/command/args; DELETE returns 204. All are owner-scoped, with CSRF for mutations.

```json
{"name":"Local evidence","transport":"stdio","command":"/absolute/path/to/server","args":[],"url":"","allowed_tools":[],"enabled":false,"timeout_seconds":10}
```

Transport is stdio or streamable-http. Stdio requires an existing absolute executable, with at most 50 args. HTTP transport requires a validated HTTPS or loopback HTTP url; command/args may be omitted. Timeout is 0.2–60 seconds. Optional bearer_token is write-only; empty string clears it. Server responses omit tokens and add id, status, last_error and bearer_token_configured. The test returns `{ok:true,server:{...},tools:[{name,description,input_schema}]}` and discovers tools without authorizing them. Available status means the last test succeeded; connections are owned/closed per operation.

No server starts automatically. Agent use requires enabled=true, an allowlist, use_mcp=true on the run and parameter-bound author approval for every external call. Changed server configuration invalidates the execution target. Schemas cannot retrieve remote references and are size/depth bounded. Arguments/results are limited to 64,000 UTF-8 bytes. The explicitly registered executable remains a trusted OS program, not a sandboxed process.

Secrets are masked on API reads but currently stored as plaintext in the backend local SQLite database (desktop permission 0600), not encrypted by OS Keychain.

## 7. Local text ingestion and index lifecycle

`POST /novels/{novel_id}/knowledge/documents` accepts:

```json
{"title":"World notes","content":"灵力必须经过月光淬炼。","source_id":"optional-stable-uuid","source_revision":1,"visibility":"approved"}
```

Content is 1–200,000 characters. Omit source_id to create a new manual source; reuse the returned source_id with a higher revision for changed text. Visibility is approved/draft/private. Returns 201 `{id,title,source_id,source_revision,visibility,status,error_message}`. A ready revision cannot change content (409). Identical ingestion is idempotent. Successful newer revisions deactivate older chunks; failed embedding requests preserve the earlier active index. Re-indexing unchanged content with a new embedding model preserves chunk IDs.

`GET .../knowledge/documents` returns a newest-first array (max 500). `DELETE .../knowledge/documents/{id}` returns 204 and deletes its chunks/FTS rows; cross-novel IDs return 404. Search continues to return only ready/active/authorized evidence. FTS absence and query embedding failures use lexical fallback. The offline script `cd apps/api && uv run python scripts/evaluate_rag.py` runs six fixed Chinese/English/isolation/version regression cases; it does not claim semantic retrieval quality.
