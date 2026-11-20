# NovelForge Agent / RAG / MCP gap analysis

Date: 2026-11-20. Runtime profile: desktop-local first, version 0.2.0.

## Scope and baseline

The starting revision was `e007504` (already committed/pushed by the coordinating agent).
The reported accepted baseline was 83 API tests, 19 frontend tests and 12 frozen-sidecar business
checks. This work changes the API/runtime, its tests, dependency/build collection and the Agent/API
documentation. Frontend and native packaging acceptance are coordinated separately; a source-mode
smoke run is not evidence that a new frozen binary has passed.

The existing implementation was useful infrastructure: typed novel-scoped tools, canon proposals
and separate author approval, optimistic chapter acceptance, knowledge provenance/version rows,
context snapshots, request IDs and tool audit rows. The gaps were in composition and lifecycle,
not a reason to replace the local application with a distributed framework.

## Findings and implemented changes

| Area | Baseline evidence/gap | Implemented executable path |
| --- | --- | --- |
| Agent execution | `ai/generation_service.py` called the provider once; no model/tool/observation loop | `ai/agent_service.py` and `agent_router.py`: persisted queued run, true asynchronous HTTP 202, finite multi-turn loop, matched call IDs, final result |
| Durable trace | Generation row had a context/output snapshot but no ordered run steps | `ai/agent_models.py`: owner+novel run, transcript, usage/elapsed budgets, sources, ordered model/tool steps with argument hashes and decisions |
| Function calling | ChatMessage held role/content; registry descriptions were not provider function envelopes | `ai/providers.py`, `openai_compatible.py`, `agent_service.model_tools`: function envelopes, assistant tool_calls, matched tool observations, validated schemas, output token allowance |
| Mock behavior | A tool-enabled mock always selected its first tool | Mock now performs a safe outline read once, then terminates after observation; scripted fixtures exercise writes and failures |
| Approval and retry | Existing direct author tool endpoint accepted approved_action; no persistent model-run approval boundary | Agent decisions bind immutable step/arguments/hash/run/owner; conditional update accepts one decision; running intent is persisted before effect; no automatic write retry |
| Budgets/cancel | Registry max_calls reset per HTTP instance; local timeout metadata was not executed | Durable run round/tool/time/token limits; four active tasks; bounded observations and args; SQLite statement progress deadline; cancellable provider waits and MCP scopes |
| Startup/shutdown | No policy for unfinished model work | Active/queued leftovers become interrupted; no replay; waiting approvals remain durable; owned task cancellation on lifespan exit |
| Retrieval | Python full-corpus lexical/cosine/RRF; no FTS accelerator | `knowledge/fts.py`: optional FTS5 trigram/BM25, quoted bounded MATCH, lifecycle triggers, filtered candidates and safe lexical fallback |
| RAG integration | Context compiler did not pass the configured embedding provider; recent-chapter option was unused | `ai/context.py`, generation/context/knowledge/analysis entry points now use author model settings; earlier chapters use current versions and exclude future/current chapter |
| Source versions | Different chapter-version UUIDs could coexist as apparently current evidence | ORM and FTS joins exclude versions not equal to chapter.current_version, retaining exact version provenance; stable manual sources deactivate older revisions |
| Ingestion lifecycle | Internal ingest service only; reingest/model changes lacked a usable user lifecycle | Novel-owned text documents list/create/delete, immutable ready source revisions, idempotency, model-tagged compatible embeddings, citation-preserving reindex, preserved old index on failure |
| MCP | No product MCP client/configuration/discovery/invocation | `ai/mcp_gateway.py`: official SDK stdio and Streamable HTTP sessions, configuration, tools/list, tools/call, ownership, timeout and cleanup |
| MCP authorization | No boundary existed because no integration existed | Disabled/empty allowlist by default; explicit per-run opt-in; all external calls await exact author decision; configuration/schema fingerprint binding; no server annotation can grant automatic write/read access |
| Model configuration | Environment-only configuration with no user entry point | `ai/local_config.py`: owner-scoped masked GET, partial PATCH, benign connection test; environment fallback and configured model propagation |
| Packaging | New SDK/schema resources absent | Migration 0013 and `scripts/build_sidecar.py` collection of MCP client/shared modules, package metadata and JSON-schema specification data; extended smoke script |

## Security and failure behavior

- Every new domain/configuration endpoint requires the existing authenticated user. Novel resources
  are resolved through owner checks; the desktop per-launch local token still wraps all requests.
  Cookie-authenticated mutations require CSRF. Cross-owner/cross-novel IDs return 404.
- Model requests cannot supply trusted approval. The decision body allows only `approve`; it cannot
  replace parameters. Canon tool approval creates a pending proposal only. Actual canon adoption
  and version-checked manuscript acceptance remain separate existing author actions.
- A running step is never automatically replayed. Repeated decision requests return 409. If the
  application stops after an external/domain effect but before recording its response, the run is
  interrupted and deliberately does not promise automatic recovery of that ambiguous operation.
- Model configuration and complete MCP server configuration are fingerprinted. Editing a server
  command/args/URL/token/allowlist after discovery invalidates the execution target. A new run is
  required rather than executing newly substituted code under an old approval.
- MCP stdio uses an explicit absolute executable and no implicit shell; model credentials are not
  inherited. No roots/sampling/elicitation capability is granted. Each SDK operation owns and closes
  its session/transport and subprocess. Discovery alone never adds a tool to the model allowlist.
- MCP schema remote references are rejected, schema depth/node/UTF-8-byte budgets apply, and schema
  validation uses a resolver that never fetches remote resources. External arguments/results are
  capped at 64,000 UTF-8 bytes after parsing. HTTP uses TLS or loopback HTTP, no inherited proxy and
  no automatic redirects. Tests use local substitutes, not real external services.
- Cancelled/interrupted runs cannot be overwritten by late model responses or use them to perform
  subsequent writes. Python cannot physically recall an already issued urllib request: the daemon
  thread may finish later at its network timeout. It has no domain-write authority. This limitation
  is documented rather than described as hard transport cancellation.
- Keys/tokens are write-only in API responses and are not included in run detail or generic error
  messages. They are currently plaintext in the local SQLite database, protected by the desktop
  database's 0600 file permission. OS Keychain/credential-manager encryption is not implemented.
- An explicitly registered stdio server is trusted local code with the user's OS privileges. This
  permission gateway is not an OS sandbox and does not make arbitrary executables safe.

## Verification

Run from repository root unless shown otherwise:

```sh
cd apps/api
uv run --extra dev pytest -q
uv run --extra dev ruff check novelforge tests alembic scripts
uv run python scripts/evaluate_rag.py
```

Observed final full API result: **118 passed** (one existing Starlette/httpx deprecation warning,
no failures); Ruff: **all checks passed**. Test modules added:

- `tests/test_agent_runtime.py`: actual multi-turn mock, matched call IDs, bound approve/reject,
  duplicate decision rejection, no canon adoption, round/tool/token/time exhaustion, true prompt
  return, cancellation/late-response discard, ownership, reused call IDs, argument tampering,
  restart state, actual post-restart waiting approval, and bounded lifespan shutdown.
- `tests/test_mcp_and_configuration.py`: actual SDK stdio discovery/call, invalid args/allowlist,
  subprocess termination, timeout cleanup, masked/owned settings, partial server patch preservation,
  real MCP approval loop, changed-configuration refusal, local HTTP model function protocol and
  configured chat/embedding IDs, Streamable HTTP discovery/call, remote schema/depth rejection.
- `tests/test_rag_lifecycle.py`: Chinese/English FTS, safe MATCH syntax, revision/deletion lifecycle,
  immutable revision and citation-preserving model reindex, hard novel/private filters, missing FTS
  plus failed embedding fallback, configured context embeddings, recent/future chapter boundary,
  and exclusion of superseded chapter versions.

The six-case JSON corpus in `tests/fixtures/rag_regression.json` and
`scripts/evaluate_rag.py` completed **6/6 deterministic checks** with zero external model requests.
It checks Chinese, English, private visibility, cross-novel exclusion and old/new revisions. This
is not a semantic-retrieval benchmark, statistical effect estimate or writing-quality score.

Migration tests include fresh/up/down/up and legacy create_all detection, including optional FTS
shadow-table handling. The desktop head assertion is now `20261120_0013`. No real user database is
used by these tests.

`scripts/smoke_desktop.py` now has **16 checks**. It was run successfully against a temporary
source-sidecar wrapper with isolated data: authenticated authoring/version conflicts, generation
acceptance, retrieval, masked settings, asynchronous two-round agent, real SDK stdio discovery,
restart persistence, configured local HTTP models, SDK tools/call after durable author approval,
matched observation, duplicate-decision refusal and host EOF shutdown. This source-mode execution
does not replace the coordinating agent's final frozen-sidecar/DMG/native UI acceptance. The exact
same script is used for the frozen binary:

```sh
python scripts/smoke_desktop.py --sidecar /absolute/path/to/novelforge-api-target
```

All processes launched for these tests (temporary HTTP model/MCP servers and source-sidecar
instances) are owned by fixtures/context managers and closed. Stdio fixtures assert their child
PIDs no longer exist. No new persistent background service is installed or left running.

## Requested tool applicability and packaging review

The explicitly requested Build macOS Apps `packaging-notarization` and `build-run-debug` skills
were read for the backend packaging/lifecycle review. NovelForge is a Tauri/Rust macOS host with a
Python sidecar, not an Xcode or SwiftPM application, so adding a separate Swift build pipeline would
be inappropriate. The coordinating agent owns `script/build_and_run.sh` and the Codex Run action;
both were inspected and already point to the existing native build/launch workflow.

The sidecar build collects MCP client/shared dynamic modules, MCP package metadata/data,
JSON-schema specification resources and referencing metadata, together with Alembic migrations.
Real SDK stdio and Streamable HTTP tests demonstrate source imports and cleanup; the same
16-check smoke script must additionally pass on the final frozen artifact. No claim of new
Developer ID signing or notarization is inferred from source settings: final bundle/signature/DMG
validation remains the coordinating agent's artifact-level acceptance.

The inspected native host starts a dedicated sidecar process group, closes stdin on exit, waits
four seconds, then kills only that group's remaining processes. The Python watcher requests server
shutdown on EOF; lifespan cancels owned agent tasks, waits at most two seconds, and records safe
interrupted states. A regression verifies exit in under two seconds while a model request remains
blocked. The SDK closes normal/cancelled stdio children; the native process-group fallback covers
unresponsive sidecar descendants. An arbitrary external executable that deliberately detaches
itself remains outside the stated non-sandboxed trust boundary.

The requested CircleCI applicability check found `.github/workflows/ci.yml` and
`.github/workflows/release-packaging.yml`, with no `.circleci` configuration or CircleCI failure.
CircleCI skills were therefore not applied and no duplicate CI service was introduced. Product
Design/Figma belong to the separate UI agent's design review; this backend task did not create or
claim a Figma artifact. No additional agents were spawned for this closeout.

The four-active-task admission check now also applies before recording/rescheduling an approval
decision. Capacity rejection returns 429 without changing the waiting step or consuming its
decision; both approve/reject retries are covered after capacity becomes available.

## Remaining real limitations

1. The agent is a bounded single-author local task, not a durable distributed worker. There is no
   general crash replay/resume API. Waiting approval is recoverable; ambiguous executing effects
   are deliberately interrupted and require author inspection/new work.
2. Token counts are heuristic plus provider usage, including tool-schema estimates and requested
   max_tokens. A vendor may use different tokenization/field semantics; this is not a billing cap.
3. Exact vector retrieval still loads authorized chunks and computes cosine in Python. Mock vectors
   have no semantic meaning. Large-corpus ANN performance, real tokenizer profiles, reranking and
   Chinese narrative retrieval quality need an actual model/corpus evaluation before claims.
4. Paragraph chunking remains the existing bounded character heuristic. It is not an implemented
   semantic chunker, overlapping sentence-aware parser or document-conversion pipeline.
5. Credentials lack OS Keychain encryption. MCP processes are not sandboxed; output size checks
   apply to parsed results, not an adversarial server's entire transport byte stream. OAuth, secret
   references, shared connection pooling and remote multi-user quotas are not implemented.
6. Local tool SQL deadlines do not forcibly preempt arbitrary Python code or every database lock
   wait. The product registry exposes only bounded built-in operations; no arbitrary handler/plugin
   code is accepted from a model.
7. Existing generation/analysis endpoints remain synchronous compatibility paths. Only the new
   Agent routes implement prompt-return asynchronous background execution and cancellable waits.
8. Audit input summaries are size-limited local author data rather than universally redacted logs.
   Rich operational metrics, retention controls and cryptographically sealed audit storage remain
   production-hardening work.

Multi-agent orchestration, Redis, PostgreSQL/pgvector and Docker were not added because they do not
solve a demonstrated desktop requirement here. The existing local database, revision workflow,
sidecar lifecycle and native distribution remain the authority for this product profile.
