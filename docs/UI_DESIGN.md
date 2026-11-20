# NovelForge writing room

Updated 2026-11-20 for 0.2.0. The implementation targets the macOS Tauri desktop application. The existing narrow-window layout is retained as a useful fallback; Android and other platforms are not a release acceptance target.

## Design decisions

The manuscript is the primary surface: warm paper, dark ink, a restrained green for actions, local system fonts, and a comfortable serif reading face for prose. No remote font, image service, generated illustration, telemetry, or user manuscript upload is needed to render the interface. Lucide supplies the existing icon vocabulary.

- The New project control and first-project empty state open a three-step guided setup for story premise and an optional opening chapter. The integration preserves a successful novel if its chapter transaction fails; a chapter retry does not duplicate the novel. The title field remains a quick-create path for experienced writers.
- The left rail holds the library, manuscript chapters, knowledge, and Agent studio. Chapter titles are no longer a long horizontal tab strip above the writing surface.
- The manuscript has a compact format switch, live count of Latin words and CJK characters, explicit save status, and `⌘/Ctrl+S`. Focus mode removes the surrounding rails without changing the document.
- The inspector switches between immutable version history and an explanation of author-controlled AI suggestions. Smaller windows can explicitly open the inspector; history is not silently removed from the workflow.
- Knowledge and Agent studio use the available center width instead of retaining an unrelated chapter-history rail. Empty states explain the next useful action. Errors remain visible with retry actions where appropriate.
- The model label says **configured**, rather than claiming a connection test passed merely because configuration exists. A mock provider is explicitly labelled in both the application header and each mock Agent task.
- Settings use a labelled modal dialog, keyboard focus containment, Escape, and focus restoration. Existing configuration must load successfully before writes are enabled. New MCP connections start disabled, with no implicit tool permissions.

The local editor owns its draft while changing workspace sections. Existing navigation guards, in-flight save revision tracking, ETags, immutable restoration, format-conversion checks, and explicit AI preview acceptance remain intact. The interface also warns before a browser/WebView unload with unsaved edits. Approving an Agent action is blocked while the manuscript is dirty; rejecting or cancelling remains available.

## Skills and tools inspected

The inventory distinguishes files on disk, advertised tools, and capabilities actually exercised. No configuration secret, environment value, token, or header was read or recorded.

| Location / family | Observed inventory | Selection |
| --- | --- | --- |
| `~/.codex/skills` | `autoresearch`, `grill-me`, `jupyter-notebook`, `pdf`, `playwright`, `pptx`, `screenshot` | Read Playwright workflow and guardrails; actual UI control used CUA only. |
| `~/.codex/skills/.system` | `imagegen`, `openai-docs`, `review-agent`, `skill-creator`, `skill-installer` | No bitmap asset was needed for a text-focused writing desk. |
| Curated Product Design | index, audit, user-context, get-context, design-qa, ideate, image-to-code, research, share, url-to-code | Read index, audit, user-context, critical overrides; ran saved-context preflight (no saved context). Existing code and current screenshots provided the design target. |
| Curated Figma | 12 entrypoints including figma-use, generate-design/library, design-to-code, create-new-file, motion, FigJam and Slides | Read figma-use; probed the official MCP with `whoami`. No file or frame was supplied, and no Figma write was attempted. |
| Curated Build macOS Apps | AppKit, SwiftUI, Liquid Glass, build/debug, packaging, signing, telemetry, tests, windows | Available but not needed for this React/Tauri UI ownership. Native packaging and runtime acceptance belong to the main agent. The project was not rewritten in SwiftUI. |
| Curated Build Web Apps on disk | frontend-app-builder, frontend-testing-debugging, react-best-practices and other entrypoints | Inspected the instructions. Used the relevant React principles: independent requests in parallel, primitive polling dependencies, effect cleanup, and separate feature components. No new frontend starter was created. |
| Curated CircleCI | builds, cli, config, chunk | No `.circleci` configuration exists; the repository uses GitHub Actions. No second CI system was added. |
| Other developer-provided roots | 6 document/spreadsheet/presentation/template entrypoints in primary runtime; 4 LaTeX/visualization entrypoints in bundled plugins; 91 skill files across the curated cache at inspection time | Present on disk, outside this UI task. Presence was not treated as a live service connection. |

| Session capability | Observed status and use |
| --- | --- |
| Official Figma MCP | 47 advertised tools; `whoami` succeeded. The returned plan seat was **View**. Authentication is verified; file edit access was not asserted. No actual novel content was transmitted. |
| CUA browser control | Chrome extension connected and used successfully. The browser inventory exposed Chrome and no in-app browser surface, so the existing Chrome connection was used with a separate test tab. All actual UI input used `cua_repl`. |
| FastCtx | No FastCtx tool appeared in the session's `ALL_TOOLS`; filesystem inspection used `rg`, batched shell reads and Python. |
| Codex app | 35 advertised app tools. The relevant UI task used normal local file/process tools; no remote app write was required. |
| Artifact session / Node REPL / Consensus | Respectively 3 / 3 / 5 advertised tools in the inspected metadata. These services were not required or probed, so their connectivity is unverified. |

## Real API integration

All calls pass through the existing `api.ts` boundary. Tauri still obtains a dynamic loopback origin and local authorization from `get_runtime_info`; the browser development build still uses the same-origin Vite proxy. No model key or MCP bearer token is written into the frontend bundle, browser storage, or logs.

| Surface | Contract consumed |
| --- | --- |
| Manuscript | Existing `/novels`, chapters, ETag PATCH, versions and restore; generation preview/accept; analysis proposal review. |
| Knowledge | `GET /novels/{id}/knowledge/search` and `GET/POST .../documents`. Sources retain chunk/document/source identity, revision, content and type. Manual material defaults to draft; approval/private visibility is explicit. Indexing explains use of the configured embedding provider. |
| Agent | `GET/POST /novels/{id}/agent/runs`, `GET /{run}`, `POST /{run}/cancel`, `POST /{run}/steps/{step}/decision`. Polling shows queued/running/waiting-approval/terminal status, exact arguments, tool results, errors and source revisions. Approval sends only `{approve}` to the existing step. MCP participation defaults to false per task. |
| Model settings | `GET/PATCH /settings/ai`, `POST /settings/ai/test`. Reads are masked; a blank key entry preserves the saved key, and a separate clear action sends an explicit empty key. Timeout matches the API's 1–120-second range. |
| MCP settings | `GET/POST /mcp/servers`, partial `PATCH /{id}`, `POST /{id}/test`, `DELETE /{id}`. Discovery shows tool descriptions and individual allowlist checkboxes; enable/disable uses a partial patch. HTTP credentials are write-only and only their configured status is shown. Removal requires a separate confirmation within the product. |

The default mock Agent is a genuine persisted execution loop with deterministic model output; it is not represented as model intelligence. The UI does not simulate successful tools, invent sources, or adopt a proposal into canon automatically.

## Validation evidence

The UI run used a dedicated SQLite database under the chat workspace's `work/ui-qa/`, a synthetic local account, a fabricated Chinese novel, and local protocol fixtures only. It did not read or modify the user's production application database, use a paid model, or send manuscript content to Figma or another external service.

CUA exercised these flows against the running API:

1. Sign-in, chapter loading, Markdown-to-rich-text conversion, save to a new immutable version, reload, and sign-out.
2. Masked model settings, local mock connection test, settings persistence, and restoration to mock after protocol testing.
3. Manual knowledge ingestion, approved-material search, expanded source excerpt and source revision.
4. A mock Agent run with model → `read_outline` → model steps and cited material.
5. A loopback OpenAI-compatible **synthetic protocol stub**, explicitly named `local-ui-protocol-stub`, requesting `propose_canon`. The UI showed waiting approval, displayed exact arguments, approved the existing step, and reached success. A second task was cancelled while awaiting approval. No canon entity was adopted.
6. A local stdio MCP fixture: add disabled → test/discover `lookup` → explicitly allow `lookup` → enable → disable. The remove confirmation was also inspected. DELETE behavior is covered by the frontend/API regression tests.
7. Desktop at the actual 1470×665 browser viewport, plus an incidental 390×844 narrow-window check for manuscript, inspector and Agent. The narrow layout had `scrollWidth === innerWidth` (390). Temporary viewport overrides were reset.

The browser showed meaningful rendered content, no framework overlay, and no relevant console errors/warnings on the final reload. Screenshots were saved outside the repository in the chat deliverables directory, `outputs/novelforge-ui/`: desktop manuscript, settings, knowledge sources, mock task, approval, MCP discovery, and narrow-window evidence. Two narrow screenshots were recaptured with CUA's documented CDP screenshot capability after the high-level screenshot wrapper returned a scaled thumbnail; the rejected thumbnails were replaced.

At the final integrated checkpoint, `npm test` passed 47 tests, and lint, typecheck and production build passed. Tests cover the original editing regressions plus immutable step approval, cancellation, dirty-draft protection, sources, mock labels, bounded tasks, service failure retry, masked credentials, key preservation/clearing, settings-load failure, MCP creation and confirmed deletion. This count includes the onboarding component tests and the App integration regressions for guided setup, unsaved manuscript protection across workspace sections, and the desktop save shortcut. The main agent independently repeated the integrated checks before freezing the macOS build.

## Limits

- Native Tauri/macOS packaging and bundled-sidecar verification are performed by the main agent after integration; the browser run does not replace that acceptance.
- No live paid provider, remote MCP service or external Figma design file was used. Protocol fixtures validate integration behavior, not model quality.
- Screenshot and keyboard checks do not constitute a complete accessibility certification. Secondary text was strengthened during visual review; full screen-reader and contrast auditing remain separate work.
- Vite reports the existing editor-heavy JavaScript bundle above 500 kB. The build succeeds; further editor splitting is a performance follow-up, not a reason to weaken synchronous format-conversion safety.
