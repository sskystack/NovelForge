#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v uv >/dev/null || { echo "Install uv first: https://docs.astral.sh/uv/" >&2; exit 1; }
command -v python3 >/dev/null || { echo "Python 3.12+ is required." >&2; exit 1; }
command -v node >/dev/null || { echo "Install Node.js 20+ first." >&2; exit 1; }
command -v npm >/dev/null || { echo "npm is required." >&2; exit 1; }

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else "Python 3.12+ is required")'
node -e 'if (Number(process.versions.node.split(".")[0]) < 20) process.exit(1)' || {
  echo "Node.js 20+ is required." >&2
  exit 1
}

uv sync --directory "$repo_root/apps/api" --extra dev --locked
npm --prefix "$repo_root/apps/web" ci
echo "NovelForge development dependencies are ready."
