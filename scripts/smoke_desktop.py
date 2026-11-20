"""Exercise the actual frozen service with isolated data and no developer API server."""

import argparse
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request
from uuid import uuid4


@contextmanager
def sidecar(binary: Path, data_dir: Path, provider=None):
    env = {**os.environ, "AI_PROVIDER": "mock", "AI_CHAT_MODEL": "mock-chat",
           "AI_EMBEDDING_MODEL": "mock-embedding", "NO_PROXY": "127.0.0.1,localhost"}
    for key in ("PYTHONPATH", "PYTHONHOME", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH"):
        env.pop(key, None)
    if os.name != "nt":
        env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    if provider:
        env.update(provider)
    with (data_dir.parent / "sidecar-smoke.stderr.log").open("a") as log:
        process = subprocess.Popen([str(binary), "--data-dir", str(data_dir), "--watch-stdin"],
                                   cwd=data_dir.parent, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log, text=True)
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
        try:
            line = lines.get(timeout=50)
            if not line:
                raise RuntimeError("Frozen sidecar exited before its handshake; inspect smoke stderr")
            runtime = json.loads(line)
            opener = request.build_opener(request.ProxyHandler({}))
            headers = {"Origin": "tauri://localhost", "X-NovelForge-Local-Token": runtime["apiToken"]}

            def call(method, path, body=None, *, expected=200, extra=None, raw=False):
                payload = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
                req = request.Request(runtime["apiOrigin"] + path, data=payload, method=method,
                                      headers={"Content-Type": "application/json", **headers, **(extra or {})})
                try:
                    response = opener.open(req, timeout=15)
                except error.HTTPError as exc:
                    response = exc
                content = response.read()
                assert response.status == expected, (method, path, response.status, content[:1000])
                return (content if raw else json.loads(content) if content else None), response.headers

            deadline = time.monotonic() + 5
            while True:
                try:
                    call("GET", "/ready")
                    break
                except error.URLError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.05)
            yield call, headers, runtime["apiOrigin"]
        finally:
            if process.stdin:
                process.stdin.close()
            try:
                result = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise AssertionError("Frozen service did not exit after its host pipe closed") from None
            assert result == 0, f"Frozen service exited with {result}"


def run(binary: Path, data_dir: Path) -> dict:
    checks = []
    credentials = {"email": f"packaged-{uuid4().hex}@example.com", "password": "isolated smoke password"}
    with sidecar(binary, data_dir) as (call, headers, first_origin):
        call("POST", "/api/v1/auth/register", {**credentials, "display_name": "Smoke writer"}, expected=201)
        _, login = call("POST", "/api/v1/auth/login", credentials)
        headers["Authorization"] = "Bearer " + login["X-NovelForge-Session"]
        novel, _ = call("POST", "/api/v1/novels", {"title": "打包回归 Smoke novel"}, expected=201)
        base = f"/api/v1/novels/{novel['id']}"
        chapter, meta = call("POST", base + "/chapters", {"title": "第一章"}, expected=201)
        path = base + f"/chapters/{chapter['id']}"
        call("PATCH", path, {"content_format": "markdown", "markdown": "# 正文\n\nSmoke evidence **中文**\n\n> 引用"}, extra={"If-Match": meta["ETag"]})
        call("PATCH", path, {"summary": "stale"}, extra={"If-Match": '"1"'}, expected=409)
        checks.extend(["register and bearer login", "create project and chapter", "save and reject stale ETag"])
        draft, _ = call("POST", base + "/ai/generations", {"chapter_id": chapter["id"]}, expected=202)
        assert draft["status"] == "succeeded"
        current, _ = call("GET", path)
        assert current["current_version"] == 2
        call("POST", base + f"/ai/generations/{draft['id']}/accept", {"expected_version": 2})
        versions, _ = call("GET", path + "/versions")
        analysis, _ = call("POST", base + f"/ai/analysis/{versions[0]['id']}", expected=202)
        assert analysis["status"] == "succeeded"
        search, _ = call("GET", base + "/knowledge/search?" + parse.urlencode({"query": "Smoke evidence 中文"}))
        assert search["results"]
        call("POST", base + "/ai/tools/read_characters/execute", {"arguments": {"query": "主角"}})
        checks.extend(["generation preview and explicit acceptance", "analysis and knowledge retrieval", "registered tool execution"])
        archive, _ = call("GET", base + "/export", raw=True)
        imported, _ = call("POST", "/api/v1/novels/import", archive, expected=201, extra={"Content-Type": "application/zip"})
        assert imported["id"] != novel["id"]
        call("POST", "/api/v1/auth/logout", expected=204)
        call("GET", "/api/v1/auth/me", expected=401)
        checks.extend(["project archive export/import", "bearer logout revocation"])
    checks.append("frozen sidecar exits on host EOF")

    models = []

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            models.append(body["model"])
            if self.path.endswith("embeddings"):
                payload = {"data": [{"index": i, "embedding": [0.2, 0.8]} for i, _ in enumerate(body["input"])]}
            else:
                content = json.dumps({"summary": "测试摘要", "events": [], "character_states": [], "consistency_warnings": []}) if "response_format" in body else "Configured provider draft"
                payload = {"model": body["model"], "choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
            encoded = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sidecar(binary, data_dir, {
            "AI_PROVIDER": "openai-compatible", "AI_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
            "AI_API_KEY": "test-placeholder", "AI_CHAT_MODEL": "smoke-chat", "AI_EMBEDDING_MODEL": "smoke-embedding",
        }) as (call, headers, second_origin):
            _, login = call("POST", "/api/v1/auth/login", credentials)
            headers["Authorization"] = "Bearer " + login["X-NovelForge-Session"]
            projects, _ = call("GET", "/api/v1/novels")
            assert novel["id"] in {item["id"] for item in projects}
            base = f"/api/v1/novels/{novel['id']}"
            chapter, _ = call("POST", base + "/chapters", {"title": "Provider test"}, expected=201)
            draft, _ = call("POST", base + "/ai/generations", {"chapter_id": chapter["id"]}, expected=202)
            assert draft["status"] == "succeeded" and draft["model"] == "smoke-chat"
            versions, _ = call("GET", base + f"/chapters/{chapter['id']}/versions")
            analysis, _ = call("POST", base + f"/ai/analysis/{versions[0]['id']}", expected=202)
            assert analysis["status"] == "succeeded"
            call("GET", base + "/knowledge/search?query=Smoke")
            assert "smoke-embedding" in models and "smoke-chat" in models
            assert "mock-embedding" not in models and "mock-chat" not in models
            checks.extend(["restart preserves projects", "configured chat and embedding models", "frozen provider loads bundled TLS certificates"])
    finally:
        server.shutdown()
        server.server_close()
    return {"status": "passed", "checks": checks, "isolated_data": str(data_dir),
            "dynamic_ports": [first_origin, second_origin], "external_model_requests": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="novelforge-packaged-smoke-") as directory:
        result = run(args.sidecar.resolve(), Path(directory) / "中文 workspace")
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
