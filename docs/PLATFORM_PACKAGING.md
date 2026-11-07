# NovelForge — Platform and Packaging Specification

**Current priority:** Desktop-Local First. This is a target specification; no Tauri shell or install artifacts existed at audited revision `27360af`.

## Product distribution targets

| Platform | Artifact | Initial operating mode |
|---|---|---|
| Windows 10/11 x64 | `.exe` installer (Tauri NSIS) | First-priority local desktop target; planned |
| macOS Apple Silicon | `.dmg` | First-priority local desktop target; planned |
| macOS Intel | `.dmg` if supported by native build/signing | Compatibility decision remains open |
| Android | Signed `.apk` | Deferred; outside current development stage |
| Web | Developer-run shared UI | Development surface, not a current SaaS deliverable |

## Desktop implementation

- Use Tauri 2 as the native shell and React/Vite as the shared UI. Avoid Next.js server-side rendering in the shared app so it can be packaged as static assets.
- Bundle the Python/FastAPI local service as a platform-specific sidecar executable. The Tauri host starts it, waits for a health check, restarts only under a bounded policy, and terminates it cleanly.
- Desktop target uses SQLite. Keep database and retrieval access behind SQLAlchemy/service adapters and design a tested SQLite-compatible migration path before changing persistent structures.
- Local lexical retrieval targets SQLite FTS5 plus a vector adapter. Current code has neither FTS5 nor pgvector retrieval; do not claim either is implemented or claim parity between them.
- Store the database, attachments, logs and backups under the OS-standard application data directory, never beside the installed executable.
- Bind the local API to loopback only. Use an ephemeral per-launch credential or equivalent local IPC authorization; validate Origin and CSRF protections. Never expose the local service on `0.0.0.0` by default.
- Installer upgrades must preserve user data and run versioned migrations with backup/rollback protection.

## Deferred Android direction

- Use Tauri 2 Android packaging for the shared UI. Android does not embed the Python sidecar, PostgreSQL or Redis.
- Android v1 requires a configured SaaS/self-hosted API endpoint. Use OS-backed secure storage for credentials.
- The editor must persist pending local edits before network operations and clearly indicate unsynced state. Full offline-first sync and conflict resolution are explicitly later milestones.
- Test APK installation, login, API error handling, file attachment permissions and screen-size/accessibility behavior on physical/emulated devices.

## Planned desktop build and release

- CI should use native Windows and macOS runners; cross-compilation is not assumed to work for every native dependency.
- Planned artifacts: Windows x64 installer `.exe` and macOS arm64 `.dmg` (x64 support remains a decision). Android `.apk` is deferred.
- Release builds should be code-signed. macOS distribution outside local development requires Developer ID signing and notarization for a smooth Gatekeeper experience. Windows signing is strongly recommended to reduce SmartScreen warnings.
- Signing certificates, Apple credentials and Android keystore material live only in CI secrets. Never commit them.
- Publish checksums, version, supported OS versions and known limitations alongside each release.
- Docker is not a prerequisite for development, installation, operation or release. Container deployment may be documented as an optional community contribution only if requested later.

## Acceptance gates

1. A clean Windows/macOS machine with no Python, Node.js, PostgreSQL or Docker can install and run the desktop app.
2. Local projects persist across close/reopen, backup/restore and upgrade; uninstall data retention is documented.
3. No local API listener is reachable from the LAN by default; sidecar lifecycle and local authorization are tested.
4. Windows and macOS release artifacts are reproducible in CI and smoke-tested.
