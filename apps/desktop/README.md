# NovelForge Desktop

This Tauri 2 shell reuses `apps/web` as its static frontend. The local FastAPI sidecar must bind to `127.0.0.1` and use an OS application-data directory for SQLite and backups. Sidecar supervision, signed installers and migration-on-upgrade are release tasks; signing keys belong only in CI secrets.
