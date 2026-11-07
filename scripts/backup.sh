#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="${NOVELFORGE_BACKUP_DIR:-$repo_root/backups}"
mkdir -p "$backup_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$backup_dir/novelforge-$timestamp.zip"
if [[ -z "${NOVELFORGE_USER_ID:-}" || -z "${NOVELFORGE_NOVEL_ID:-}" ]]; then
  echo "Set NOVELFORGE_USER_ID and NOVELFORGE_NOVEL_ID to scope this backup." >&2
  exit 2
fi
uv run --directory "$repo_root/apps/api" python -m novelforge.projects.archive_cli export "$archive" --user-id "$NOVELFORGE_USER_ID" --novel-id "$NOVELFORGE_NOVEL_ID"
echo "$archive"
