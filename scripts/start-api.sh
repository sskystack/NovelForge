#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
uv run --directory "$repo_root/apps/api" alembic upgrade head
exec uv run --directory "$repo_root/apps/api" uvicorn novelforge.main:app --host "${NOVELFORGE_HOST:-127.0.0.1}" --port "${NOVELFORGE_PORT:-8000}"
