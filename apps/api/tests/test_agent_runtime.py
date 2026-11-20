import threading
import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_canon import create_novel, headers, register_and_login

from novelforge.ai.agent_models import AgentRun, AgentStep
from novelforge.ai.agent_service import recover_interrupted
from novelforge.ai.providers import ChatResponse, MockProvider, ToolCall
from novelforge.canon.models import CanonProposal, Character
from novelforge.database import Base, create_database_engine
from novelforge.main import create_app
from novelforge.settings import Settings


def start(client, **payload):
    register_and_login(client)
    novel_id = create_novel(client, "Agent fixture")
    base = f"/api/v1/novels/{novel_id}/agent/runs"
    response = client.post(
        base, headers=headers(client), json={"prompt": "检查人物和大纲", **payload}
    )
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "queued"
    return base, response.json()["id"]


def wait_run(client, base, run_id, statuses=("succeeded", "failed", "waiting_approval")):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        response = client.get(f"{base}/{run_id}")
        assert response.status_code == 200, response.text
        result = response.json()
        if result["status"] in statuses:
            return result
        time.sleep(0.01)
    pytest.fail(f"Agent did not reach {statuses}: {result}")


class ScriptedProvider(MockProvider):
    def __init__(self, name="read_characters", arguments=None, *, repeat=False):
        self.name = name
        self.arguments = {"query": "林"} if arguments is None else arguments
        self.messages = []
        self.repeat = repeat

    def chat(self, messages, *, model, tools=(), response_schema=None, max_output_tokens=None):
        self.messages.append(messages)
        if len(self.messages) == 1 or self.repeat:
            return ChatResponse(
                "",
                (ToolCall(f"call-{len(self.messages)}", self.name, self.arguments),),
                model=model,
                prompt_tokens=1,
                completion_tokens=1,
            )
        return ChatResponse("Checked the tool observation.", model=model)


def test_mock_agent_runs_real_multiturn_and_finishes(client):
    base, run_id = start(client)
    run = wait_run(client, base, run_id)
    assert run["status"] == "succeeded", run
    assert run["is_mock"] is True and run["tools_used"] == 1
    assert [step["kind"] for step in run["steps"]] == ["model", "tool", "model"]
    assert all(step["status"] == "succeeded" for step in run["steps"])


def test_tool_observation_matches_model_call_id(client, monkeypatch):
    fixture = ScriptedProvider()
    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: fixture)
    base, run_id = start(client)
    run = wait_run(client, base, run_id)
    assert run["status"] == "succeeded", run
    final_messages = fixture.messages[-1]
    assert final_messages[-2].tool_calls[0].id == "call-1"
    assert final_messages[-1].role == "tool" and final_messages[-1].tool_call_id == "call-1"


@pytest.mark.parametrize("approve", [True, False])
def test_canon_proposal_requires_bound_author_decision_and_never_adopts(
    client, db_session, monkeypatch, approve
):
    fixture = ScriptedProvider(
        "propose_canon",
        {"entity_type": "character", "proposed_data": {"name": "待审人物"}, "rationale": "Fixture"},
    )
    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: fixture)
    base, run_id = start(client)
    run = wait_run(client, base, run_id)
    assert run["status"] == "waiting_approval", run
    assert db_session.scalar(select(CanonProposal.id)) is None
    step = next(item for item in run["steps"] if item["status"] == "waiting_approval")
    assert len(step["arguments_hash"]) == 64
    decision = client.post(
        f"{base}/{run_id}/steps/{step['id']}/decision",
        json={"approve": approve},
        headers=headers(client),
    )
    assert decision.status_code == 202, decision.text
    run = wait_run(client, base, run_id, statuses=("succeeded", "failed"))
    assert run["status"] == "succeeded", run
    repeat = client.post(
        f"{base}/{run_id}/steps/{step['id']}/decision",
        json={"approve": approve},
        headers=headers(client),
    )
    assert repeat.status_code == 409
    proposals = db_session.scalars(select(CanonProposal)).all()
    assert len(proposals) == (1 if approve else 0)
    assert all(str(proposal.status) == "pending" for proposal in proposals)
    assert db_session.scalar(select(Character.id)) is None


@pytest.mark.parametrize(
    "limits,expected",
    [
        ({"max_rounds": 1}, "round"),
        ({"max_tool_calls": 1}, "tool call"),
        ({"max_tokens": 100}, "token"),
    ],
)
def test_agent_budgets_terminate_loops(client, monkeypatch, limits, expected):
    fixture = ScriptedProvider(repeat=True)
    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: fixture)
    base, run_id = start(client, **limits)
    result = wait_run(client, base, run_id, statuses=("failed",))
    assert expected in result["error"]


def test_http_returns_promptly_and_cancel_discards_late_model_result(client, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    class Slow(MockProvider):
        def chat(self, *args, **kwargs):
            entered.set()
            release.wait(3)
            return ChatResponse(
                "Late output",
                (
                    ToolCall(
                        "late",
                        "propose_canon",
                        {"entity_type": "character", "proposed_data": {"name": "Must not execute"}},
                    ),
                ),
            )

    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: Slow())
    try:
        started = time.monotonic()
        base, run_id = start(client)
        assert time.monotonic() - started < 1.5
        assert entered.wait(2)
        cancelled = client.post(f"{base}/{run_id}/cancel", headers=headers(client))
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        release.set()
        time.sleep(0.05)
        result = client.get(f"{base}/{run_id}").json()
        assert result["status"] == "cancelled" and not result["output"]
        assert not any(step["tool_name"] == "propose_canon" for step in result["steps"])
    finally:
        release.set()


def test_agent_time_budget_terminates_wait(client, monkeypatch):
    class Slow(MockProvider):
        def chat(self, *args, **kwargs):
            time.sleep(0.3)
            return ChatResponse("Late result")

    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: Slow())
    base, run_id = start(client, max_seconds=0.1)
    result = wait_run(client, base, run_id, statuses=("failed",))
    assert "time budget" in result["error"]


def test_unknown_tool_and_self_approval_cannot_write(client, monkeypatch):
    fixture = ScriptedProvider(
        "propose_canon",
        {"entity_type": "character", "proposed_data": {"name": "No"}, "approved_action": True},
    )
    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: fixture)
    base, run_id = start(client)
    run = wait_run(client, base, run_id)
    assert run["status"] == "waiting_approval"
    step = run["steps"][-1]
    assert (
        client.post(
            f"{base}/{run_id}/steps/{step['id']}/decision",
            headers=headers(client),
            json={"approve": True, "arguments": {}},
        ).status_code
        == 422
    )


def test_restart_marks_active_runs_interrupted_and_retains_waiting(client, db_session):
    base, run_id = start(client)
    wait_run(client, base, run_id)
    row = db_session.get(AgentRun, UUID(run_id))
    row.status = "running"
    db_session.commit()
    recover_interrupted(client.app)
    db_session.expire_all()
    assert db_session.get(AgentRun, UUID(run_id)).status == "interrupted"
    row = db_session.get(AgentRun, UUID(run_id))
    row.status = "waiting_approval"
    db_session.commit()
    recover_interrupted(client.app)
    db_session.expire_all()
    assert db_session.get(AgentRun, UUID(run_id)).status == "waiting_approval"


def test_agent_run_is_bound_to_novel_and_owner(client):
    base, run_id = start(client)
    wait_run(client, base, run_id)
    other = create_novel(client, "Other novel")
    assert client.get(f"/api/v1/novels/{other}/agent/runs/{run_id}").status_code == 404
    client.post("/api/v1/auth/logout", headers=headers(client))
    register_and_login(client, email="other-agent@example.com")
    assert client.get(f"{base}/{run_id}").status_code == 404


def test_reused_tool_call_id_fails_without_replaying(client, monkeypatch):
    class Reuse(ScriptedProvider):
        def chat(self, *args, **kwargs):
            return ChatResponse("", (ToolCall("same", "read_outline", {}),))

    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: Reuse())
    base, run_id = start(client)
    result = wait_run(client, base, run_id, statuses=("failed",))
    assert "reused" in result["error"] and result["tools_used"] == 1


def test_corrupted_approval_arguments_are_rejected(client, monkeypatch, db_session):
    fixture = ScriptedProvider(
        "propose_canon", {"entity_type": "character", "proposed_data": {"name": "A"}}
    )
    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: fixture)
    base, run_id = start(client)
    result = wait_run(client, base, run_id)
    step = db_session.get(AgentStep, UUID(result["steps"][-1]["id"]))
    step.arguments = {**step.arguments, "rationale": "Changed behind the approval UI"}
    db_session.commit()
    response = client.post(
        f"{base}/{run_id}/steps/{step.id}/decision", json={"approve": True}, headers=headers(client)
    )
    assert response.status_code == 409


@pytest.mark.parametrize("approve", [True, False])
def test_decision_capacity_rejection_preserves_undecided_step(client, monkeypatch, approve):
    fixture = ScriptedProvider(
        "propose_canon", {"entity_type": "character", "proposed_data": {"name": "Capacity fixture"}}
    )
    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: fixture)
    base, run_id = start(client)
    waiting = wait_run(client, base, run_id)
    assert waiting["status"] == "waiting_approval"
    step_id = waiting["steps"][-1]["id"]
    # Simulate four independently active tasks without starting artificial model
    # requests. Rejection must precede the durable decision compare-and-set.
    tasks = client.app.state.agent_tasks
    occupied = [f"capacity-fixture-{index}" for index in range(4)]
    for key in occupied:
        tasks[key] = object()
    try:
        response = client.post(
            f"{base}/{run_id}/steps/{step_id}/decision",
            headers=headers(client),
            json={"approve": approve},
        )
        assert response.status_code == 429, response.text
        assert response.json()["code"] == "AGENT_CAPACITY"
        detail = client.get(f"{base}/{run_id}").json()
        assert detail["status"] == "waiting_approval"
        assert detail["steps"][-1]["decision"] is None
        assert detail["steps"][-1]["status"] == "waiting_approval"
    finally:
        for key in occupied:
            tasks.pop(key, None)
    response = client.post(
        f"{base}/{run_id}/steps/{step_id}/decision",
        headers=headers(client),
        json={"approve": approve},
    )
    assert response.status_code == 202, response.text
    result = wait_run(client, base, run_id, statuses=("succeeded", "failed"))
    assert result["status"] == "succeeded", result


def test_waiting_approval_resumes_after_real_app_restart(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'restart.db'}", session_cookie_secure=True
    )
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    fixture = ScriptedProvider(
        "propose_canon",
        {"entity_type": "character", "proposed_data": {"name": "Restart-safe proposal"}},
    )
    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: fixture)
    with TestClient(create_app(settings, engine), base_url="https://testserver") as client:
        base, run_id = start(client)
        waiting = wait_run(client, base, run_id)
        assert waiting["status"] == "waiting_approval", waiting
        cookies = client.cookies
    # New app and engine, with no in-memory continuation or future from the old run.
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        client.cookies.update(cookies)
        detail = client.get(f"{base}/{run_id}").json()
        assert detail["status"] == "waiting_approval"
        response = client.post(
            f"{base}/{run_id}/steps/{detail['steps'][-1]['id']}/decision",
            headers=headers(client),
            json={"approve": True},
        )
        assert response.status_code == 202, response.text
        result = wait_run(client, base, run_id, statuses=("succeeded", "failed"))
        assert result["status"] == "succeeded", result
        assert result["tools_used"] == 1


def test_lifespan_stops_pending_model_wait_within_host_exit_window(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    class Slow(MockProvider):
        def chat(self, *args, **kwargs):
            entered.set()
            release.wait(5)
            return ChatResponse("Abandoned model result")

    monkeypatch.setattr("novelforge.ai.agent_service.create_chat_provider", lambda _: Slow())
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'shutdown.db'}", session_cookie_secure=True
    )
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    try:
        with TestClient(create_app(settings, engine), base_url="https://testserver") as client:
            base, run_id = start(client)
            assert entered.wait(2)
            cookies = client.cookies
            stopping = time.monotonic()
        assert time.monotonic() - stopping < 2
        with TestClient(create_app(settings), base_url="https://testserver") as client:
            client.cookies.update(cookies)
            assert client.get(f"{base}/{run_id}").json()["status"] == "interrupted"
    finally:
        release.set()
