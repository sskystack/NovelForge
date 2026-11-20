"""Packaged local API: own its socket, migrate first, and stop when its host exits."""

import argparse
import json
import logging
import os
import secrets
import socket
import sys
import threading
from collections.abc import Sequence
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn

from novelforge.desktop_database import initialize_database, sqlite_url


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="NovelForge desktop local service")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--watch-stdin", action="store_true")
    args = parser.parse_args(argv)
    data_dir = args.data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    data_dir.chmod(0o700)
    log_dir = data_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "api.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    database_path = data_dir / "novelforge.db"
    initialize_database(database_path)
    local_token = secrets.token_urlsafe(32)
    os.environ.update(
        {
            "APP_ENV": "desktop",
            "DATABASE_URL": sqlite_url(database_path),
            "LOCAL_API_TOKEN": local_token,
            "SESSION_COOKIE_SECURE": "false",
            "SESSION_COOKIE_SAMESITE": "strict",
            "CORS_ORIGINS": (
                "tauri://localhost,http://tauri.localhost,https://tauri.localhost,"
                "http://localhost:5173,http://127.0.0.1:5173"
            ),
        }
    )
    # Import after configuring the local profile; never initialize PostgreSQL here.
    from novelforge.main import app

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", args.port))
    port = listener.getsockname()[1]
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            print(
                json.dumps({"apiOrigin": f"http://127.0.0.1:{port}", "apiToken": local_token}),
                flush=True,
            )
            yield

    app.router.lifespan_context = lifespan
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            loop="asyncio",
            http="h11",
            ws="none",
            lifespan="on",
            log_config=None,
            access_log=False,
        )
    )
    if args.watch_stdin:

        def watch_host() -> None:
            # Pipe EOF also handles host crashes and PyInstaller's child process.
            if sys.stdin is not None:
                sys.stdin.buffer.read()
            server.should_exit = True

        threading.Thread(target=watch_host, name="desktop-host-watch", daemon=True).start()
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
