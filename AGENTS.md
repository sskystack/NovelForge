# NovelForge project instructions

## Maintained platform — macOS only

Effective 2026-11-20, the product owner explicitly requires maintaining **macOS only**.
This instruction supersedes historical Windows/Android/multi-platform plans in older documents.

- Target the Tauri 2 macOS desktop app, bundled FastAPI sidecar, and per-user SQLite data.
- macOS Apple Silicon is the currently validated distribution target. Do not claim Intel support
  without a native build and verification.
- Do not implement Android features, build APKs, maintain Android compatibility, or add Windows
  release gates. Existing mobile/Windows scaffolds are historical, unsupported artifacts.
- The Vite browser surface is for development and testing of the shared macOS UI. Responsive
  behavior is useful for small Mac windows; it is not a commitment to a mobile product.
- GitHub Actions is the repository's CI. Do not introduce a parallel CircleCI pipeline simply
  because a CircleCI skill or connector is available.
- Revisit another platform only after an explicit, later product-owner instruction.

## Runtime and data invariants

- Never replace the dynamic loopback handshake with a hardcoded API port. Preserve launch-token
  authorization, authenticated ownership, CSRF for cookie sessions, and masked secret responses.
- Keep user data out of the repository, app bundle, browser assets, logs, and test fixtures.
  Use temporary data or `NOVELFORGE_DATA_DIR` for verification. The development Run action defaults
  to ignored `.local-data/`; actual application data uses the OS application-support directory.
- Use versioned Alembic migrations and a verified backup before updating existing databases.
  Unknown database schemas must fail visibly rather than being silently stamped.
- A model cannot approve its own actions. Preserve explicit author approval, exact tool arguments,
  immutable chapter versions, optimistic concurrency, and preview-before-accept behavior.
- Cancelled/interrupted runs cannot be overwritten by late model results or replay ambiguous writes.
- Maintain host/sidecar shutdown and MCP child-process cleanup. Do not leave test servers running.

## Working and validation

- Coordinate file ownership when using multiple agents; do not undo another worker's changes.
- Read the applicable skill before using it. Use Product Design/Figma/macOS build skills where
  they materially help; do not send private manuscripts to external design or model services.
- Do not copy source from GPL or unverified-license reference projects. Borrow interaction ideas
  with source attribution and implement them independently.
- Validate API changes with `uv run --directory apps/api --extra dev pytest` and Ruff; frontend
  changes with `npm test`, lint, typecheck, and build in `apps/web`.
- New runtime dependencies must also pass the frozen sidecar smoke test. Source tests alone do
  not establish that the standalone app works.
- Use `script/build_and_run.sh` for the macOS development build/run loop. Validate the actual DMG,
  nested code signatures, native UI workflows, upgrade preservation, and process cleanup before
  claiming a desktop release passed.
- Ad-hoc signing is local integrity verification, not Developer ID signing or Apple notarization.
  Report that distinction accurately.
