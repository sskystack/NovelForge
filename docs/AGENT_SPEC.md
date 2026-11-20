# NovelForge — local Agent, RAG and MCP runtime (0.2.0)

This describes executable behavior, not a proposed distributed-agent architecture. The runtime remains a FastAPI modular monolith with SQLite and a packaged sidecar. No Redis, Docker, PostgreSQL server, paid model or separate agent framework is required by the desktop profile.

## 1. Durable run state

`POST /api/v1/novels/{novel_id}/agent/runs` persists a queued run and returns HTTP 202 before execution. An application-owned asyncio task drives the model → tools → observations → model loop. This differs from the older `/ai/generations` and `/ai/analysis` preview APIs, which still execute synchronously despite their historical 202 response code.

Each run belongs to one authenticated owner and novel. Its persisted transcript records assistant tool calls and matching `tool_call_id` observations. Ordered model/tool steps retain status, arguments, argument SHA-256, results and errors. Root `sources` holds exact passages, document/chunk IDs and revisions. API responses omit private model/MCP configuration fingerprints.

States: queued, running, waiting_approval, succeeded, failed, cancelled, interrupted. Multiple tool calls in one model turn are observed before another model request. Reused/duplicate call IDs fail closed. The offline mock performs one outline read and finishes after its observation; it never fabricates a write request.

Defaults: 6 model rounds, 12 tool calls, 60 active seconds and 12,000 estimated aggregate tokens; at most four active tasks per sidecar. Budgets are checked before each model/tool operation. The provider receives a remaining output allowance as `max_tokens`; reported and locally estimated usage is checked afterwards. The Chinese/Latin estimator is not a model tokenizer or a vendor billing guarantee. A server refusing the output-limit field fails the run rather than receiving an unlimited retry.

Cancellation persists state and cancels the waiting task. Network model/embedding requests run in daemon threads without domain-write permissions. An already issued urllib request cannot be forcibly stopped: it may continue to its network timeout. Its late result is discarded and cannot trigger subsequent tool writes. Local SQLite handlers use a statement progress deadline; this does not preempt arbitrary Python code.

Shutdown cancels active tasks and records interrupted state. Startup marks leftover queued/running runs interrupted without replaying them. Waiting approvals remain inspectable and can be decided after restart. There is no general crash-resume/retry API. If a write completed but recording its result was interrupted, the run is explicitly interrupted and the write is never automatically retried.

## 2. Tools and author control

| Permission | Tools | Actual effect |
| --- | --- | --- |
| Read | read_characters, read_worldbuilding, read_timeline, read_outline, search_chapters | Read the authorized novel; structured canon reads use approved facts |
| Draft | draft_outline, draft_summary | Return JSON previews; do not save outlines, summaries or manuscript text |
| Propose | propose_canon | After author decision, create a pending canon proposal only |

The model receives standard OpenAI function-tool envelopes. Built-in arguments use Pydantic schemas with `extra=forbid`, and are validated again at execution. Canon proposed_data is open-ended JSON, so the adapter does not claim universal OpenAI `strict:true` support. Canon service validation still applies. Results are bounded structured JSON, not universal Pydantic output schemas.

A write request is persisted with an immutable step and argument hash. The authenticated author decides that exact step through a CSRF-protected endpoint accepting only `approve`, never replacement arguments or a model approval flag. A conditional update records one decision. The step is marked running before execution; duplicate clicks/retries cannot authorize or replay the same effect. Rejections become tool observations.

Calls use the existing audit table with novel, tool, status, duration and a size-limited input summary including run ID. Full results remain in the owned run. Inputs are size-limited local author data, not guaranteed secret-redacted text.

No accept_generation, approve_canon, raw SQL, filesystem or shell execution tool is exposed to the model. Manuscript acceptance still requires an expected version. Formal canon adoption remains a separate author approval/revision transaction. Approving the propose_canon tool does not approve the resulting canon proposal.

## 3. RAG and context

Retrieval fuses optional SQLite FTS5 trigram/BM25, deterministic Chinese-character/Latin-word lexical scoring, and exact Python cosine similarity for compatible stored embeddings using reciprocal rank fusion. Migration/ingestion detects FTS capability. Unsupported builds, missing FTS and short queries fall back safely to lexical scoring. Bounded quoted MATCH terms prevent raw user MATCH syntax. FTS candidates are filtered before their limit, then intersected again with the ORM-authorized set.

All ranking streams enforce novel ID, ready-document status, visibility and active chunks. Approved visibility is default. Only the explicit knowledge-search draft option includes drafts; private documents are not returned to the agent. Chapter-version documents are joined to the chapter current version so obsolete prose is not retrieved as current evidence. Exact version UUID provenance remains available for historical inspection.

Manual ingestion uses a stable source UUID/revision. A ready revision's content is immutable; changed content needs a new revision. Successful newer ingestion deactivates earlier source chunks. Failed embedding requests preserve prior active content. Idempotent ingestion preserves chunk IDs; model-only reindex updates embeddings without breaking citations. Embeddings carry a model ID; mismatched model/dimension vectors do not participate in cosine ranking. Insert/update/delete triggers maintain FTS. Document deletion cascades chunks and removes their FTS entries.

The context compiler prioritizes canon, applies story-time state/event selection, passes the configured embedding provider/model into retrieval, and includes bounded earlier chapters at current versions. Current/future chapters are excluded from the recent block. Sections retain source/provenance, estimated tokens and omission warnings. Consistency checking remains a separate deterministic API; context assembly does not claim to resolve every semantic contradiction.

The vector adapter intentionally remains exact local Python over SQLite JSON vectors, suitable for the current small desktop corpus rather than large-scale ANN search. Mock embeddings are SHA-256-derived and have no semantic-quality claim. Learned reranking, real tokenizers and a task-specific model profile manager are not implemented.

## 4. Actual MCP client

The product uses the official MCP Python SDK ClientSession with stdio and Streamable HTTP transports. Codex's own MCP tools are unrelated. Registrations are author-scoped, disabled by default, with an empty allowlist. Stdio requires an existing absolute executable path and does not implicitly invoke a shell. A narrow environment excludes model keys; the SDK supplies its standard OS environment. No roots, model sampling or elicitation capability is granted.

Explicit connection tests discover all tools without granting permission. Agent use additionally requires use_mcp=true, an enabled registration, a tool allowlist and an author decision for every external call. Untrusted server annotations never grant automatic read permission.

Each operation owns its session/transport, overall timeout, initialization, tools/list or tools/call, and cleanup. Available means the last connection test succeeded, not that a live idle socket exists. No arbitrary service starts at application launch. Stdio servers require their own installed executable. Streamable HTTP supports HTTPS or explicit loopback HTTP, verified TLS, optional write-only bearer token, no inherited HTTP proxy and no automatic redirects.

Tools are aliased for the model and bound to server ID, original name, schema and full configuration hash. Changing command, args, URL, token or allowlist after discovery invalidates the run's execution target. The author must start a new run. Remote $ref/$dynamicRef/$recursiveRef references are rejected. Schema byte/depth/node limits and a no-network resolver prevent hidden schema fetches. Tool arguments and returned JSON have a 64,000 UTF-8-byte limit.

Approval is not an OS sandbox. An explicitly trusted local executable runs with the user's OS privileges; remote servers receive approved tool arguments. The UI makes this opt-in explicit.

## 5. Settings and migration

/settings/ai supplies author-scoped mock/OpenAI-compatible configuration and a connection test without manuscript text. Masked reads reveal only whether a key exists. Settings apply to agent, generation, analysis, context and knowledge retrieval; environment values are fallback. Keys/tokens are backend-only and never returned in API responses, but are stored as plaintext in the local SQLite database (desktop file permission 0600). OS Keychain encryption is not implemented.

Migration 20261120_0013 adds run/step/config/server tables and optional FTS resources. Legacy detection ignores only named FTS virtual/shadow tables and still checks domain tables/columns. Version-12 databases use the existing backed-up migration path. The sidecar build collects SDK/schema resources.

## 6. Verification and limits

See AGENT_GAP_ANALYSIS.md for evidence and commands. Tests use temporary SQLite databases, local model HTTP substitutes and temporary MCP servers. No paid provider, real API key or user manuscript is required. The six-case RAG corpus is a tiny lexical/boundary regression set, not a semantic benchmark.

Distributed orchestration, multi-agent delegation, Redis queues and a general plugin shell are deliberately absent for this single-author desktop application. Remaining production work includes OS secret storage, model-specific tokenization/quality evaluation, large-corpus indexing, stronger process sandboxing, richer observability and remote multi-user scheduling.
