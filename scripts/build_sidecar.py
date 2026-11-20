"""Build a native, reproducible sidecar from any current working directory."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    api = root / "apps/api"
    desktop = root / "apps/desktop"
    parser = argparse.ArgumentParser()
    parser.add_argument("--target")
    args = parser.parse_args()
    rust = subprocess.check_output(["rustc", "-vV"], text=True)
    host = next(line.removeprefix("host: ") for line in rust.splitlines() if line.startswith("host: "))
    target = args.target or host
    if target != host:
        parser.error("Python sidecars must be built on their native target; cross-compilation is unsupported.")
    suffix = ".exe" if "windows" in target else ""
    binaries = desktop / "src-tauri/binaries"
    command = [
        "uv", "run", "--directory", str(api), "--extra", "dev", "python", "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--name", "novelforge-api",
        "--distpath", str(binaries), "--workpath", str(desktop / ".pyinstaller-work"),
        "--specpath", str(desktop / ".pyinstaller-spec"), "--paths", str(api),
        "--add-data", f"{api / 'alembic'}{os.pathsep}alembic",
        "--hidden-import", "alembic.ddl.sqlite",
        "--hidden-import", "uvicorn.loops.asyncio",
        "--hidden-import", "uvicorn.protocols.http.h11_impl",
        "--hidden-import", "uvicorn.lifespan.on",
        "--copy-metadata", "email-validator",
        "--collect-submodules", "mcp.client",
        "--collect-submodules", "mcp.shared",
        "--collect-data", "mcp",
        "--copy-metadata", "mcp",
        "--collect-data", "jsonschema_specifications",
        "--copy-metadata", "jsonschema",
        "--copy-metadata", "jsonschema-specifications",
        "--copy-metadata", "referencing",
        str(api / "novelforge/desktop_entry.py"),
    ]
    subprocess.run(command, cwd=api, check=True)
    result = binaries / f"novelforge-api-{target}{suffix}"
    shutil.move(str(binaries / f"novelforge-api{suffix}"), result)
    print(json.dumps({"sidecar": str(result), "target": target}))


if __name__ == "__main__":
    main()
