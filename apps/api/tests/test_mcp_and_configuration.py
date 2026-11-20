import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from test_agent_runtime import ScriptedProvider, wait_run
from test_canon import create_novel, headers, register_and_login

from novelforge.ai import mcp_gateway
from novelforge.ai.providers import ChatResponse, ToolCall


@pytest.fixture
def mcp_fixture(tmp_path):
    script = tmp_path / "mcp_fixture.py"
    pids = tmp_path / "pids.jsonl"
    script.write_text("""import asyncio, json, os, sys
from mcp.server.fastmcp import FastMCP
from pathlib import Path
Path(__file__).with_name("pids.jsonl").open("a").write(json.dumps(os.getpid()) + "\\n")
app = FastMCP("NovelForge isolated fixture", host="127.0.0.1",
    port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000, stateless_http=True)
@app.tool()
def lookup(query: str) -> dict:
    return {"query": query, "inherited_secret": os.getenv("NOVELFORGE_TEST_SECRET", "")}
@app.tool()
async def slow(query: str) -> dict:
    await asyncio.sleep(20)
    return {"query": query}
if __name__ == "__main__":
    app.run(transport="streamable-http" if len(sys.argv) > 1 else "stdio")
""")
    config = {
        "name": "Isolated fixture",
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(script)],
        "allowed_tools": ["lookup"],
        "enabled": True,
        "timeout_seconds": 5,
    }
    yield config
    # Both successful and cancelled SDK contexts must terminate every child.
    if pids.exists():
        for line in pids.read_text().splitlines():
            with pytest.raises(ProcessLookupError):
                os.kill(int(line), 0)


def test_sdk_stdio_discovers_calls_validates_and_closes_process(mcp_fixture, monkeypatch):
    monkeypatch.setenv("NOVELFORGE_TEST_SECRET", "must-not-be-inherited")

    async def exercise():
        all_tools = await mcp_gateway.discover(mcp_fixture, allowed_only=False)
        assert {tool["name"] for tool in all_tools} == {"lookup", "slow"}
        tools = await mcp_gateway.discover(mcp_fixture)
        assert [tool["name"] for tool in tools] == ["lookup"]
        result = await mcp_gateway.call(
            mcp_fixture, "lookup", {"query": "中文 evidence"}, tools[0]["input_schema"]
        )
        assert "中文 evidence" in json.dumps(result, ensure_ascii=False)
        assert "must-not-be-inherited" not in json.dumps(result)
        with pytest.raises(ValueError, match="allowlisted"):
            await mcp_gateway.call(mcp_fixture, "slow", {"query": "x"}, tools[0]["input_schema"])
        with pytest.raises(Exception, match="required"):
            await mcp_gateway.call(mcp_fixture, "lookup", {}, tools[0]["input_schema"])

    asyncio.run(exercise())


def test_sdk_stdio_timeout_closes_child(mcp_fixture):
    config = {**mcp_fixture, "allowed_tools": ["slow"], "timeout_seconds": 1.5}

    async def exercise():
        with pytest.raises(TimeoutError):
            await mcp_gateway.call(
                config,
                "slow",
                {"query": "timeout"},
                {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            )

    asyncio.run(exercise())


def test_mcp_registration_is_owned_masked_disabled_and_discoverable(client, mcp_fixture):
    register_and_login(client)
    server = client.post(
        "/api/v1/mcp/servers",
        headers=headers(client),
        json={
            **mcp_fixture,
            "enabled": False,
            "allowed_tools": [],
            "bearer_token": "private-fixture-token",
        },
    )
    assert server.status_code == 201, server.text
    data = server.json()
    assert data["enabled"] is False and data["bearer_token_configured"] is True
    assert "private-fixture-token" not in server.text
    patched = client.patch(
        f"/api/v1/mcp/servers/{data['id']}", headers=headers(client), json={"enabled": True}
    )
    assert patched.status_code == 200 and patched.json()["enabled"] is True
    assert patched.json()["command"] == mcp_fixture["command"]
    assert patched.json()["bearer_token_configured"] is True
    patched = client.patch(
        f"/api/v1/mcp/servers/{data['id']}",
        headers=headers(client),
        json={"allowed_tools": ["lookup"]},
    )
    assert patched.status_code == 200 and patched.json()["allowed_tools"] == ["lookup"]
    tested = client.post(f"/api/v1/mcp/servers/{data['id']}/test", headers=headers(client))
    assert tested.status_code == 200, tested.text
    assert {tool["name"] for tool in tested.json()["tools"]} == {"lookup", "slow"}
    assert tested.json()["server"]["status"] == "available"
    client.post("/api/v1/auth/logout", headers=headers(client))
    register_and_login(client, email="second-config@example.com")
    assert client.get("/api/v1/mcp/servers").json() == []
    assert client.get(f"/api/v1/mcp/servers/{data['id']}").status_code == 404


def test_agent_mcp_call_waits_for_approval_and_uses_sdk(client, monkeypatch, mcp_fixture):
    register_and_login(client)
    config = client.post("/api/v1/mcp/servers", headers=headers(client), json=mcp_fixture).json()

    class MCPModel(ScriptedProvider):
        def chat(self, messages, *, model, tools=(), **kwargs):
            if any(message.role == "tool" for message in messages):
                assert "fixture observation" in messages[-1].content
                return ChatResponse("MCP observation received.")
            alias = next(
                tool["function"]["name"]
                for tool in tools
                if tool["function"]["name"].startswith("mcp_")
            )
            return ChatResponse(
                "", (ToolCall("mcp-call", alias, {"query": "fixture observation"}),)
            )

    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: MCPModel())
    novel_id = create_novel(client, "MCP run")
    base = f"/api/v1/novels/{novel_id}/agent/runs"
    response = client.post(
        base, headers=headers(client), json={"prompt": "Use lookup", "use_mcp": True}
    )
    run_id = response.json()["id"]
    result = wait_run(client, base, run_id)
    assert result["status"] == "waiting_approval", result
    assert result["steps"][-1]["tool_name"].startswith("mcp_")
    step_id = result["steps"][-1]["id"]
    response = client.post(
        f"{base}/{run_id}/steps/{step_id}/decision", headers=headers(client), json={"approve": True}
    )
    assert response.status_code == 202, response.text
    result = wait_run(client, base, run_id, statuses=("succeeded", "failed"))
    assert result["status"] == "succeeded", result
    second = client.post(
        base, headers=headers(client), json={"prompt": "Use lookup again", "use_mcp": True}
    ).json()
    second = wait_run(client, base, second["id"])
    assert second["status"] == "waiting_approval", second
    assert (
        client.patch(
            f"/api/v1/mcp/servers/{config['id']}",
            headers=headers(client),
            json={"allowed_tools": ["lookup", "slow"]},
        ).status_code
        == 200
    )
    response = client.post(
        f"{base}/{second['id']}/steps/{second['steps'][-1]['id']}/decision",
        headers=headers(client),
        json={"approve": True},
    )
    assert response.status_code == 202
    changed = wait_run(client, base, second["id"], statuses=("failed",))
    assert "registration changed" in changed["error"]
    # Changing an approved target can never silently change a later execution.
    assert (
        client.delete(f"/api/v1/mcp/servers/{config['id']}", headers=headers(client)).status_code
        == 204
    )


def test_model_settings_are_write_only_and_used_by_local_http_protocol(client):
    requests = []

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            if self.path.endswith("embeddings"):
                payload = {
                    "data": [
                        {"index": i, "embedding": [0.5, 0.5]} for i in range(len(body["input"]))
                    ]
                }
            elif body.get("tools") and not any(
                message["role"] == "tool" for message in body["messages"]
            ):
                payload = {
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "protocol-call",
                                        "type": "function",
                                        "function": {"name": "read_outline", "arguments": "{}"},
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                }
            else:
                payload = {
                    "choices": [
                        {"message": {"content": "Protocol verified."}, "finish_reason": "stop"}
                    ]
                }
            encoded = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        register_and_login(client)
        response = client.patch(
            "/api/v1/settings/ai",
            headers=headers(client),
            json={
                "provider": "openai-compatible",
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "chat_model": "local-protocol-chat",
                "embedding_model": "local-protocol-embed",
                "api_key": "synthetic-not-real-secret",
            },
        )
        assert response.status_code == 200 and response.json()["api_key_configured"] is True
        assert "synthetic-not-real-secret" not in response.text
        assert client.post("/api/v1/settings/ai/test", headers=headers(client)).status_code == 200
        novel_id = create_novel(client, "Protocol")
        base = f"/api/v1/novels/{novel_id}"
        ingested = client.post(
            base + "/knowledge/documents",
            headers=headers(client),
            json={"title": "Evidence", "content": "中文知识与 local protocol evidence"},
        )
        assert ingested.status_code == 201, ingested.text
        created = client.post(
            base + "/agent/runs",
            headers=headers(client),
            json={"prompt": "local protocol evidence"},
        )
        result = wait_run(client, base + "/agent/runs", created.json()["id"])
        assert result["status"] == "succeeded" and result["provider"] == "openai-compatible", result
        assert result["sources"] and result["output"] == "Protocol verified."
        final = [
            body
            for body in requests
            if any(message.get("role") == "tool" for message in body.get("messages", []))
        ][-1]
        assert final["messages"][-1]["tool_call_id"] == "protocol-call"
        assert final["messages"][-2]["tool_calls"][0]["id"] == "protocol-call"
        assert final["max_tokens"] > 0
        assert {body["model"] for body in requests} == {
            "local-protocol-chat",
            "local-protocol-embed",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_remote_plaintext_model_endpoint_is_rejected(client):
    register_and_login(client)
    response = client.patch(
        "/api/v1/settings/ai",
        headers=headers(client),
        json={"base_url": "http://untrusted.example/v1"},
    )
    assert response.status_code == 422


def test_sdk_streamable_http_lists_and_calls(mcp_fixture):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen(
        [mcp_fixture["command"], *mcp_fixture["args"], str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    pytest.fail("Isolated MCP HTTP fixture did not start")
                time.sleep(0.03)
        config = {
            "transport": "streamable-http",
            "url": f"http://127.0.0.1:{port}/mcp",
            "allowed_tools": ["lookup"],
            "timeout_seconds": 3,
        }

        async def exercise():
            tools = await mcp_gateway.discover(config)
            assert [tool["name"] for tool in tools] == ["lookup"]
            result = await mcp_gateway.call(
                config, "lookup", {"query": "HTTP fixture"}, tools[0]["input_schema"]
            )
            assert "HTTP fixture" in json.dumps(result)

        asyncio.run(exercise())
    finally:
        process.terminate()
        process.wait(timeout=3)


@pytest.mark.parametrize("keyword", ["$ref", "$dynamicRef", "$recursiveRef"])
def test_mcp_schema_cannot_trigger_remote_reference_requests(keyword):
    with pytest.raises(ValueError, match="Remote"):
        mcp_gateway.validate_input_schema(
            {
                "type": "object",
                "properties": {
                    "unsafe": {keyword: "https://must-not-be-contacted.invalid/schema.json"}
                },
            }
        )
    nested = {"type": "object"}
    for _ in range(25):
        nested = {"properties": {"nested": nested}}
    with pytest.raises(ValueError, match="depth"):
        mcp_gateway.validate_input_schema(nested)
