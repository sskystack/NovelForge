# NovelForge — Platform and Packaging Specification

> **Owner decision — 2026-11-20: macOS only.** Android, Windows and other platforms are no longer maintained, built or released. Historical multi-platform plans below do not authorize new work or create acceptance gates. Read the repository `AGENTS.md` first; current Agent/RAG/MCP implementation evidence is in `docs/AGENT_GAP_ANALYSIS.md`.

**Current target:** macOS Apple Silicon DMG. The standalone app/sidecar exists and is validated locally; Intel support requires a separate native build and validation. Ad-hoc signing is not Developer ID signing or Apple notarization.

## Product distribution targets

| Platform | Artifact | Initial operating mode |
|---|---|---|
| Windows | No release | Unmaintained historical scaffold |
| macOS Apple Silicon | `.dmg` | Only maintained distribution target |
| macOS Intel | `.dmg` if supported by native build/signing | Compatibility decision remains open |
| Android | No release | Unmaintained historical scaffold; no APK jobs |
| Web | Developer-run shared UI | Development surface, not a current SaaS deliverable |

## Desktop implementation

- Use Tauri 2 as the native shell and React/Vite as the shared UI. Avoid Next.js server-side rendering in the shared app so it can be packaged as static assets.
- Bundle the Python/FastAPI local service as a platform-specific sidecar executable. The Tauri host starts it, waits for a health check, restarts only under a bounded policy, and terminates it cleanly.
- Desktop target uses SQLite. Keep database and retrieval access behind SQLAlchemy/service adapters and design a tested SQLite-compatible migration path before changing persistent structures.
- Local lexical retrieval targets SQLite FTS5 plus a vector adapter. Optional FTS5 is implemented with lexical fallback; exact vector retrieval remains a local adapter, without pgvector parity or large-corpus ANN claims.
- Store the database, attachments, logs and backups under the OS-standard application data directory, never beside the installed executable.
- Bind the local API to loopback only. Use an ephemeral per-launch credential or equivalent local IPC authorization; validate Origin and CSRF protections. Never expose the local service on `0.0.0.0` by default.
- Installer upgrades must preserve user data and run versioned migrations with backup/rollback protection.

## Historical Android direction — unmaintained

- Use Tauri 2 Android packaging for the shared UI. Android does not embed the Python sidecar, PostgreSQL or Redis.
- Android v1 requires a configured SaaS/self-hosted API endpoint. Use OS-backed secure storage for credentials.
- The editor must persist pending local edits before network operations and clearly indicate unsynced state. Full offline-first sync and conflict resolution are explicitly later milestones.
- Test APK installation, login, API error handling, file attachment permissions and screen-size/accessibility behavior on physical/emulated devices.

## Planned desktop build and release

- CI and release jobs use macOS runners; Python sidecars must be built for their native target.
- Maintained artifact: macOS arm64 `.dmg`. Android APK and Windows installer jobs have been removed.
- Release builds should be code-signed. macOS distribution outside local development requires Developer ID signing and notarization for a smooth Gatekeeper experience. Windows signing is strongly recommended to reduce SmartScreen warnings.
- Signing certificates, Apple credentials and Android keystore material live only in CI secrets. Never commit them.
- Publish checksums, version, supported OS versions and known limitations alongside each release.
- Docker is not a prerequisite for development, installation, operation or release. Container deployment may be documented as an optional community contribution only if requested later.

## Acceptance gates

1. The macOS Apple Silicon app bundles its runtime; a clean-machine distribution test is separate from local validation.
2. Local projects persist across close/reopen, backup/restore and upgrade; uninstall data retention is documented.
3. No local API listener is reachable from the LAN by default; sidecar lifecycle and local authorization are tested.
4. macOS release artifacts are built and smoke-tested. No Android/Windows acceptance gates apply.
