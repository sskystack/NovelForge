# NovelForge Android — unmaintained historical scaffold

Effective 2026-11-20, the product owner requires macOS-only development. Do not build, release, test or extend Android from this scaffold. The project-level `AGENTS.md` overrides the historical plan below; returning to mobile requires an explicit later owner instruction.

The Android target uses the shared Vite UI through Tauri 2 Android packaging and connects to a configured SaaS or self-hosted API. Store session tokens in Android secure storage and preserve unsaved editor drafts before network requests. No Python sidecar or PostgreSQL runs on the device.
