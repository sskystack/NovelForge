#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
case "$MODE" in
  run|--verify|verify|--debug|debug|--logs|logs|--telemetry|telemetry) ;;
  *) printf 'Usage: %s [run|--verify|--debug|--logs|--telemetry]\n' "$0" >&2; exit 2 ;;
esac

if [[ "$(uname -s)" != Darwin ]]; then
  printf 'This entrypoint builds the macOS app. Use the native Tauri build on other systems.\n' >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_BUNDLE="$ROOT_DIR/apps/desktop/src-tauri/target/release/bundle/macos/NovelForge.app"
APP_BINARY="$APP_BUNDLE/Contents/MacOS/novelforge-desktop"
DATA_DIR="${NOVELFORGE_DATA_DIR:-$ROOT_DIR/.local-data}"

# Stop only the development bundle owned by this entrypoint, never /Applications.
uv run --project "$ROOT_DIR/apps/api" --extra dev python - "$APP_BINARY" <<'PY'
import os
import signal
import subprocess
import sys
import time

target = sys.argv[1]
def pids():
    output = subprocess.check_output(["ps", "-axo", "pid=,comm="], text=True)
    return [int(parts[0]) for line in output.splitlines()
            if len(parts := line.strip().split(None, 1)) == 2 and parts[1] == target]

for pid in pids():
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
deadline = time.monotonic() + 8
while pids() and time.monotonic() < deadline:
    time.sleep(0.1)
if pids():
    raise SystemExit("The development app did not stop. Close its window and retry.")
PY

cd "$ROOT_DIR"
npm run sidecar --prefix apps/desktop
(
  cd apps/desktop
  npm exec -- tauri build --bundles app
)
/usr/bin/codesign --verify --deep --strict "$APP_BUNDLE"
mkdir -p "$DATA_DIR/logs"
chmod 700 "$DATA_DIR"
printf 'Development data: %s\n' "$DATA_DIR"

open_app() {
  /usr/bin/open -n --env "NOVELFORGE_DATA_DIR=$DATA_DIR" "$APP_BUNDLE"
}

case "$MODE" in
  run) open_app ;;
  --debug|debug)
    NOVELFORGE_DATA_DIR="$DATA_DIR" lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    touch "$DATA_DIR/logs/api.log"
    open_app
    tail -n 30 -F "$DATA_DIR/logs/api.log"
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate 'process == "novelforge-desktop"'
    ;;
  --verify|verify)
    open_app
    uv run --project "$ROOT_DIR/apps/api" --extra dev python - "$APP_BINARY" <<'PY'
import subprocess
import sys
import time

for attempt in range(50):
    output = subprocess.check_output(["ps", "-axo", "comm="], text=True)
    if any(line.strip() == sys.argv[1] for line in output.splitlines()):
        print("Native app process is running; inspect the window for API readiness.")
        break
    time.sleep(0.1)
else:
    raise SystemExit("The native app process did not appear after launch.")
PY
    ;;
esac
