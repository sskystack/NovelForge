# NovelForge — Platform and Packaging Specification

## Product distribution targets

| Platform | Artifact | Initial operating mode |
|---|---|---|
| Windows 10/11 x64 | `.exe` installer (Tauri NSIS) | Local-first desktop; optional remote server |
| macOS Apple Silicon | `.dmg` | Local-first desktop; optional remote server |
| macOS Intel | `.dmg` when supported by build/signing pipeline | Same as macOS ARM |
| Android | Signed `.apk` | Remote SaaS or self-hosted server |
| Web | HTTPS web app | SaaS or self-hosted server |

## Desktop implementation

- Use Tauri 2 as the native shell and React/Vite as the shared UI. Avoid Next.js server-side rendering in the shared app so it can be packaged as static assets.
- Bundle the Python/FastAPI local service as a platform-specific sidecar executable. The Tauri host starts it, waits for a health check, restarts only under a bounded policy, and terminates it cleanly.
- Desktop local mode uses SQLite. Keep database access behind SQLAlchemy repositories and define a tested SQLite-compatible schema/migration path; PostgreSQL-only features such as pgvector must be behind adapters.
- Local retrieval starts with SQLite FTS5 plus a vector adapter. Do not claim parity with server-side pgvector until retrieval evaluation demonstrates it.
- Store the database, attachments, logs and backups under the OS-standard application data directory, never beside the installed executable.
- Bind the local API to loopback only. Use an ephemeral per-launch credential or equivalent local IPC authorization; validate Origin and CSRF protections. Never expose the local service on `0.0.0.0` by default.
- Installer upgrades must preserve user data and run versioned migrations with backup/rollback protection.

## Android implementation

- Use Tauri 2 Android packaging for the shared UI. Android does not embed the Python sidecar, PostgreSQL or Redis.
- Android v1 requires a configured SaaS/self-hosted API endpoint. Use OS-backed secure storage for credentials.
- The editor must persist pending local edits before network operations and clearly indicate unsynced state. Full offline-first sync and conflict resolution are explicitly later milestones.
- Test APK installation, login, API error handling, file attachment permissions and screen-size/accessibility behavior on physical/emulated devices.

## Build and release

- CI uses native Windows, macOS and Android runners; cross-compilation is not assumed to work for every native dependency.
- Build artifacts: Windows x64 installer `.exe`, macOS `.dmg` (arm64 initially; x64 if supported), Android `.apk`.
- Release builds should be code-signed. macOS distribution outside local development requires Developer ID signing and notarization for a smooth Gatekeeper experience. Windows signing is strongly recommended to reduce SmartScreen warnings.
- Signing certificates, Apple credentials and Android keystore material live only in CI secrets. Never commit them.
- Publish checksums, version, supported OS versions and known limitations alongside each release.
- Docker is not a prerequisite for development, installation, operation or release. Container deployment may be documented as an optional community contribution only if requested later.

## Acceptance gates

1. A clean Windows/macOS machine with no Python, Node.js, PostgreSQL or Docker can install and run the desktop app.
2. A clean Android device can install the APK and connect to a configured server.
3. App upgrades preserve local data; uninstall behavior and data retention are explicitly documented.
4. No local API listener is reachable from the LAN by default.
5. Windows, macOS and Android release artifacts are reproducible in CI and smoke-tested.

## Current repository artifacts

The native install path is `scripts/install.sh` or the existing OS-specific setup scripts. `scripts/start-api.sh` applies migrations before binding the API to loopback. `deploy/novelforge.service` and `deploy/launchd.plist.example` provide service templates. Tauri and Android packaging remain opt-in release targets; signing credentials are never stored in the repository.
