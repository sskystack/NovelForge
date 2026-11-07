# NovelForge — API Specification

Base path: `/api/v1`  
Format: JSON, UTF-8  
Authentication: opaque server-side session in an `HttpOnly`, `SameSite=Strict` cookie; bearer token for API clients (future).
All endpoints are scoped to the authenticated user and novel membership.

Browser mutations authenticated by cookies require `X-CSRF-Token`, matching the readable `novelforge_csrf` cookie. The session cookie is named `novelforge_session`, contains a random token, and is backed by a database row containing only its SHA-256 hash. Set `SESSION_COOKIE_SECURE=true` whenever the API is served over HTTPS. Auth endpoints and validation failures use `application/problem+json` with a request ID.

## 1. Common conventions

- IDs are UUID strings.
- Timestamps are ISO 8601 UTC.
- Pagination: `limit` (default 20, max 100), `cursor` (opaque).
- Errors use `application/problem+json`.
- Mutating chapter endpoints require `If-Match` or `expected_version`.
- Never accept arbitrary SQL, filesystem paths or shell commands from clients.

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

Novel endpoints require an authenticated owner. Requests for a novel owned by another user return `404` so its existence is not disclosed. The list hides archived novels by default; `GET /novels?include_archived=true` includes the current user's archived projects. `PATCH /novels/{novel_id}` with `{"status":"active"}` restores an archived novel. Create, update and archive requests require the CSRF header.

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
- `POST /novels/{novel_id}/canon/proposals/{proposal_id}/approve`
- `POST /novels/{novel_id}/canon/proposals/{proposal_id}/reject`

NF-003 provides full CRUD for characters, locations, factions and world rules under `/api/v1/novels/{novel_id}/...`. All requests require an authenticated owner; every child lookup includes both `novel_id` and entity ID, returning `404` for records outside the path novel. Collection reads return approved `canon` records by default. Authors may pass `include_non_canon=true` to inspect drafts and proposals. New records default to `draft`; direct creation or promotion to `canon` is rejected until the approval/revision workflow is implemented. Approved records cannot be edited or deleted through ordinary CRUD. Create, update and delete require the CSRF header.

Character records contain stable identity fields (`name`, `aliases`, `summary`, `personality`, `background`, `goals`, `constraints`, `attributes`). Locations and factions contain `name`, `description` and `attributes`. World rules contain `title`, `category`, `description` and structured `constraints`.

NF-004 adds `POST|GET /novels/{novel_id}/events`, `POST|GET /novels/{novel_id}/characters/{character_id}/states`, `GET /novels/{novel_id}/characters/{character_id}/state-at?story_order=N`, `GET /novels/{novel_id}/character-states?story_order=N`, and `POST|GET /novels/{novel_id}/relationships`. Character-state and relationship intervals are half-open: `valid_from_order` / `story_order` is included and `valid_to_order` is excluded. A state-at query returns the latest approved state applicable at that story order; it returns `state: null` when no approved state applies. Relationship reads show approved records by default, with `include_non_canon=true` available for review. Event references and both relationship endpoints must belong to the path novel.

### Planning and chapters
- `GET|POST /novels/{novel_id}/outlines`
- `PATCH|DELETE /novels/{novel_id}/outlines/{node_id}`
- `GET|POST /novels/{novel_id}/chapters`
- `GET|PATCH /novels/{novel_id}/chapters/{chapter_id}`
- `GET /novels/{novel_id}/chapters/{chapter_id}/versions`
- `POST /novels/{novel_id}/chapters/{chapter_id}/restore/{version_id}`
- `GET|POST /novels/{novel_id}/events`
- `GET|POST /novels/{novel_id}/foreshadowings`

### Knowledge and consistency
- `POST /novels/{novel_id}/knowledge/ingest`
- `GET /novels/{novel_id}/knowledge/search`
- `POST /novels/{novel_id}/consistency/check`
- `GET /novels/{novel_id}/consistency/issues`
- `POST /novels/{novel_id}/consistency/issues/{issue_id}/resolve`

### AI
- `GET|POST /novels/{novel_id}/ai/model-profiles`
- `POST /novels/{novel_id}/ai/generations`
- `GET /novels/{novel_id}/ai/generations/{generation_id}`
- `POST /novels/{novel_id}/ai/generations/{generation_id}/cancel`
- `POST /novels/{novel_id}/ai/generations/{generation_id}/accept`

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

`GET /api/v1/novels/{novel_id}/knowledge/search?q=林渊&limit=10`

Response:

```json
{
  "items": [
    {
      "chunk_id": "uuid",
      "source_type": "chapter",
      "source_id": "uuid",
      "source_title": "第十二章：石碑",
      "revision": 3,
      "snippet": "...",
      "score": 0.91,
      "story_order": 12
    }
  ]
}
```

### Start generation

`POST /api/v1/novels/{novel_id}/ai/generations`

```json
{
  "task": "draft_chapter",
  "chapter_id": "uuid",
  "instructions": "描写主角进入禁地后的探索，保持谨慎内敛的性格。",
  "model_profile_id": "uuid",
  "context_options": {
    "include_recent_chapters": 3,
    "include_open_foreshadowing": true,
    "story_order": 20
  },
  "output": {
    "format": "markdown",
    "max_tokens": 5000
  }
}
```

Response `202`:

```json
{
  "generation_id": "uuid",
  "status": "queued"
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
