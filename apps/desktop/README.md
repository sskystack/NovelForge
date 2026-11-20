# NovelForge Desktop

This Tauri 2 shell reuses `apps/web` as its static frontend and bundles FastAPI as a native Python sidecar. The sidecar binds an OS-assigned loopback port, sends its address and launch credential to the Rust host, initializes versioned SQLite storage, and stops when the host pipe closes. Startup failures expose a retry action and a log location.

From the repository root:

```sh
uv sync --directory apps/api --extra dev --locked
npm ci --prefix apps/web
npm ci --prefix apps/desktop
npm run tauri:build --prefix apps/desktop -- --bundles dmg
```

The sidecar build script detects the native Rust target and includes migration scripts and runtime dependencies. Cross-compiling Python sidecars is deliberately rejected. Windows uses a native Windows build with the NSIS bundle target.

On macOS, persistent data is under `~/Library/Application Support/dev.novelforge.desktop`. Logs are in `logs/api.log`; recognized legacy databases are backed up before migration. Unknown schemas fail closed rather than being silently stamped. Set `NOVELFORGE_DATA_DIR` when launching a test instance to keep fixtures separate from user projects.

The default AI provider is `mock`. Real providers currently use backend environment settings `AI_PROVIDER`, `AI_BASE_URL`, `AI_API_KEY`, `AI_CHAT_MODEL`, and `AI_EMBEDDING_MODEL`; an end-user provider-settings screen is not yet implemented. Credentials are never passed to the frontend. WebView reloads restore bearer sessions from session storage; completely closing the app may require signing in again.

macOS bundles declare a minimum system version of 11.0 and use ad-hoc signing for local verification. Developer ID signing and notarization remain separate distribution work. Windows builds have not been validated on a Windows host in this repair.

Packaged-service smoke test:

```sh
uv run --project apps/api --extra dev python scripts/smoke_desktop.py --sidecar apps/desktop/src-tauri/binaries/novelforge-api-aarch64-apple-darwin
```
