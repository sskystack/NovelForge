#!/usr/bin/env bash
set -euo pipefail
archive="${1:-}"
if [[ -z "$archive" || ! -f "$archive" ]]; then
  echo "Usage: scripts/restore.sh <archive.zip>" >&2
  exit 2
fi
if [[ -z "${NOVELFORGE_USER_ID:-}" ]]; then
  echo "Set NOVELFORGE_USER_ID to the owner of the imported project." >&2
  exit 2
fi
uv run --directory "$(cd "$(dirname "${BASH_SOURCE[0]}")/../apps/api" && pwd)" python -m novelforge.projects.archive_cli import "$archive" --user-id "$NOVELFORGE_USER_ID"
