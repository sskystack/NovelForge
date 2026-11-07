#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v uv >/dev/null || { echo "uv is required" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm is required" >&2; exit 1; }
uv sync --directory "$repo_root/apps/api" --extra dev --locked
(cd "$repo_root/apps/web" && npm ci)
echo "NovelForge dependencies installed. Configure .env before starting the API."
