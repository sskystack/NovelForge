import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from novelforge.database import Base, create_database_engine
from novelforge.desktop_database import initialize_database, sqlite_url
from novelforge.main import create_app
from novelforge.settings import Settings

LOCAL_TOKEN = "test-local-token-that-is-never-a-user-session"
ORIGINS = ("tauri://localhost", "http://tauri.localhost", "https://tauri.localhost")


@pytest.mark.parametrize("origin", ORIGINS)
def test_desktop_bearer_session_can_write_save_and_revoke(origin):
    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    app = create_app(
        Settings(
            database_url="sqlite://", local_api_token=LOCAL_TOKEN, cors_origins=",".join(ORIGINS)
        ),
        engine=engine,
    )
    headers = {"Origin": origin, "X-NovelForge-Local-Token": LOCAL_TOKEN}
    with TestClient(app) as client:
        credentials = {"email": "desktop@example.com", "password": "test password long enough"}
        assert (
            client.post(
                "/api/v1/auth/register",
                headers=headers,
                json={**credentials, "display_name": "Test writer"},
            ).status_code
            == 201
        )
        login = client.post("/api/v1/auth/login", headers=headers, json=credentials)
        assert login.status_code == 200
        token = login.headers["X-NovelForge-Session"]
        client.cookies.clear()  # WebViews may block cookies across the custom protocol boundary.
        headers["Authorization"] = f"Bearer {token}"
        novel = client.post("/api/v1/novels", headers=headers, json={"title": "Desktop"})
        assert novel.status_code == 201
        path = f"/api/v1/novels/{novel.json()['id']}/chapters"
        chapter = client.post(path, headers=headers, json={"title": "First chapter"})
        assert chapter.status_code == 201
        saved = client.patch(
            f"{path}/{chapter.json()['id']}",
            headers={**headers, "If-Match": chapter.headers["ETag"]},
            json={"content_format": "markdown", "markdown": "正文 **测试**"},
        )
        assert saved.status_code == 200
        assert saved.headers["ETag"] == '"2"'
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_local_api_requires_launch_token_and_supports_desktop_preflight():
    engine = create_database_engine("sqlite://")
    app = create_app(
        Settings(
            database_url="sqlite://", local_api_token=LOCAL_TOKEN, cors_origins=",".join(ORIGINS)
        ),
        engine=engine,
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 401
        assert (
            client.get("/ready", headers={"X-NovelForge-Local-Token": LOCAL_TOKEN}).status_code
            == 200
        )
        assert (
            client.get(
                "/health",
                headers={
                    "Origin": "https://untrusted.example",
                    "X-NovelForge-Local-Token": LOCAL_TOKEN,
                },
            ).status_code
            == 403
        )
        preflight = client.options(
            "/api/v1/novels/test/chapters/test",
            headers={
                "Origin": ORIGINS[1],
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization,if-match,x-novelforge-local-token",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["Access-Control-Allow-Origin"] == ORIGINS[1]
        assert (
            "etag"
            in client.get(
                "/health",
                headers={
                    "Origin": ORIGINS[1],
                    "X-NovelForge-Local-Token": LOCAL_TOKEN,
                },
            )
            .headers["Access-Control-Expose-Headers"]
            .lower()
        )


def test_fresh_desktop_database_is_versioned_and_restart_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///must-not-be-created.db")
    path = tmp_path / "中文 workspace" / "novel%20.db"
    assert initialize_database(path) is None
    assert initialize_database(path) is None
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20261120_0013"
        )
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_legacy_database_is_backed_up_and_preserves_data(tmp_path):
    path = tmp_path / "legacy.db"
    engine = create_database_engine(sqlite_url(path))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,password_hash,display_name,created_at,updated_at) "
                "VALUES (:id,'preserve@example.com','unused','Writer',"
                "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            {"id": "1" * 32},
        )
    engine.dispose()
    backup = initialize_database(path)
    assert backup and backup.exists()
    for candidate in (path, backup):
        with sqlite3.connect(candidate) as db:
            assert db.execute("SELECT email FROM users").fetchone()[0] == "preserve@example.com"
    assert initialize_database(path) is None


def test_partial_legacy_schema_is_rejected_without_silent_stamping(tmp_path):
    path = tmp_path / "unsupported.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE users (id TEXT PRIMARY KEY)")
        db.execute("INSERT INTO users VALUES ('preserve-me')")
    with pytest.raises(RuntimeError, match="legacy|schema"):
        initialize_database(path)
    engine = create_database_engine(sqlite_url(path))
    assert inspect(engine).get_table_names() == ["users"]
    engine.dispose()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT id FROM users").fetchone()[0] == "preserve-me"


def test_source_sidecar_uses_dynamic_port_and_exits_on_host_pipe_close(tmp_path):
    api_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(api_root), "DATABASE_URL": "invalid://ignored"}
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "novelforge.desktop_entry",
            "--data-dir",
            str(tmp_path / "中文 desktop data"),
            "--watch-stdin",
        ],
        cwd=tmp_path,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    try:
        line = lines.get(timeout=20)
        if not line:
            pytest.fail(f"Sidecar exited before readiness: {process.stderr.read()}")
        runtime = json.loads(line)
        assert runtime["apiOrigin"].startswith("http://127.0.0.1:")
        deadline = time.monotonic() + 5
        while True:
            try:
                ready = httpx.get(
                    runtime["apiOrigin"] + "/ready",
                    headers={
                        "X-NovelForge-Local-Token": runtime["apiToken"],
                    },
                    trust_env=False,
                )
                assert ready.status_code == 200
                break
            except httpx.ConnectError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.05)
        assert httpx.get(runtime["apiOrigin"] + "/health", trust_env=False).status_code == 401
        process.stdin.close()
        assert process.wait(timeout=8) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
