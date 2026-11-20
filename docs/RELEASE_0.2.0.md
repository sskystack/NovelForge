# NovelForge 0.2.0 — macOS writing workspace and agent integration

Date: 2026-11-20. Maintained target: macOS Apple Silicon. Other platforms are no longer
maintained; see the repository `AGENTS.md`.

## Delivered

- Paper-and-ink writing workspace, chapter navigation, focus mode, version inspector,
  keyboard save, and explicit loading/error/unsaved states.
- Three-step project setup: premise and genre, optional empty first chapter, and review.
  A received project-success response is preserved if the subsequent chapter request fails.
- Real Agent studio with persistent asynchronous runs, model/function/tool-result cycles,
  source records, budgets, cancellation, and parameter-bound author approvals.
- Local knowledge ingestion and retrieval, optional FTS5 acceleration, vector/lexical fusion,
  current-source-version filtering, and recent-chapter context.
- Official MCP SDK integration for stdio and Streamable HTTP; disabled registrations and
  empty allowlists by default, discovery, configuration-bound approval, and process cleanup.
- Masked model/connection settings, write-only keys, benign connection checks, and offline
  mock labels. Author acceptance and canon approval remain explicit.
- A single macOS development Run entrypoint, maintained macOS-only CI/release jobs, and
  versioned database migration with backup.

## Verification actually run

| Check | Observed result |
| --- | --- |
| API tests | 118 passed |
| Frontend tests | 47 passed |
| Python lint, frontend lint/typecheck/build | Passed |
| Fixed retrieval/boundary corpus | 6/6; zero external model requests |
| Frozen sidecar workflows | 16 checks passed, including real MCP SDK discovery/call and durable approval |
| Previous frozen release → new frozen release | SQLite V12 → V13; manuscript and chapter/version IDs preserved; backup created; zero FK violations |
| DMG-extracted app | Native launch, three-step Chinese onboarding, first chapter, Cmd-S save, Agent trace, source retrieval, masked model test, MCP discovery/allowlist/enable/disable passed |
| Bundle integrity | `codesign --verify --deep --strict` passed for the DMG-extracted app |
| Test app/MCP cleanup | No owned application, sidecar or MCP fixture processes left after host termination |

Tests use isolated directories, fabricated manuscripts, mock providers and local protocol
fixtures. No paid provider or live remote MCP service was used. Native UI testing complements
the frozen-service checks; it is not inferred from a successful TypeScript build.

## Remaining limitations

- Ad-hoc signing verifies local integrity. Developer ID signing, Apple notarization, and
  clean-machine distribution validation are not completed.
- Local provider keys and MCP credentials are masked in responses but remain plaintext inside
  the permission-restricted database; OS Keychain encryption is a follow-up.
- A registered stdio executable runs with the user's OS privileges; the tool gateway is not
  an operating-system sandbox. Parsed output limits do not bound all adversarial transport bytes.
- Runs waiting for approval can continue after restart. Ambiguous in-progress effects are marked
  interrupted and are not replayed. Token budgets are estimates, not vendor billing guarantees.
- Exact vector search and mock embeddings do not establish real semantic quality or large-corpus
  performance. Reranking, actual tokenizer profiles and writing-quality evaluation remain open.
- First-chapter goals are saved planning notes, with no persistent editing/context-injection UI yet.
  Creation has no cross-crash/network-loss idempotency guarantee; project archives are engineering
  backups, not sanitized publication exports.
- The existing editor-heavy JavaScript chunk is about 683 kB (215 kB gzip); Vite warns about size.

Detailed evidence and adoption choices: `UI_DESIGN.md`, `AGENT_GAP_ANALYSIS.md`, and
`OPEN_SOURCE_ADOPTION.md`.
