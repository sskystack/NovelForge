# NovelForge Desktop — macOS only

Effective 2026-11-20, only macOS is maintained. Android and Windows scaffolds are historical; no corresponding build, compatibility or release work is required. See the repository `AGENTS.md`.

This Tauri 2 shell reuses `apps/web` as its static frontend and bundles FastAPI as a native Python sidecar. The sidecar binds an OS-assigned loopback port, sends its address and launch credential to the Rust host, initializes versioned SQLite storage, and stops when the host pipe closes. Startup failures expose a retry action and a log location.

From the repository root:

```sh
uv sync --directory apps/api --extra dev --locked
npm ci --prefix apps/web
npm ci --prefix apps/desktop
npm run tauri:build --prefix apps/desktop -- --bundles dmg
```

The sidecar build script detects the native Rust target and includes migration scripts and runtime dependencies. Cross-compiling Python sidecars is deliberately rejected. The maintained bundle target is macOS DMG; other targets are not released.

On macOS, persistent data is under `~/Library/Application Support/dev.novelforge.desktop`. Logs are in `logs/api.log`; recognized legacy databases are backed up before migration. Unknown schemas fail closed rather than being silently stamped. Set `NOVELFORGE_DATA_DIR` when launching a test instance to keep fixtures separate from user projects.

The default AI provider is `mock`. Real providers can be configured through the local model-settings screen, with environment settings `AI_PROVIDER`, `AI_BASE_URL`, `AI_API_KEY`, `AI_CHAT_MODEL`, and `AI_EMBEDDING_MODEL` as defaults. Stored keys are masked in responses but are not yet OS Keychain encrypted. Credentials are never passed to the frontend. WebView reloads restore bearer sessions from session storage; completely closing the app may require signing in again.

macOS bundles declare a minimum system version of 11.0 and use ad-hoc signing for local verification. Developer ID signing and notarization remain separate distribution work. Windows and Android are outside current maintenance scope.

Packaged-service smoke test:

```sh
uv run --project apps/api --extra dev python scripts/smoke_desktop.py --sidecar apps/desktop/src-tauri/binaries/novelforge-api-aarch64-apple-darwin
```

## macOS application icon

The bundle explicitly includes `icons/icon.icns` and macOS PNG representations. Run `python scripts/verify_macos_bundle.py /path/to/NovelForge.dmg` after packaging to check the actual `CFBundleIconFile`, embedded icon data and nested signatures. See `docs/MACOS_ICON_PACKAGING.md`. Opening a new DMG alone does not replace an older application already in `/Applications`.
