from test_canon import create_novel, headers, register_and_login

from novelforge.ai.providers import ChatResponse


def test_analysis_is_idempotent_and_does_not_change_chapter(client):
    register_and_login(client)
    novel_id = create_novel(client, "Analysis")
    chapter = client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        headers=headers(client),
        json={"title": "First"},
    )
    assert chapter.status_code == 201
    chapter_id = chapter.json()["id"]
    saved = client.patch(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}",
        headers={**headers(client), "If-Match": '"1"'},
        json={"content_format": "markdown", "markdown": "林渊进入山谷。"},
    )
    assert saved.status_code == 200
    versions = client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/versions").json()
    version_id = versions[0]["id"]
    url = f"/api/v1/novels/{novel_id}/ai/analysis/{version_id}"
    first = client.post(url, headers=headers(client))
    second = client.post(url, headers=headers(client))
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "succeeded"
    assert first.json()["summary_candidate"]
    assert (
        client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter_id}").json()["current_version"]
        == 2
    )


def test_analysis_proposal_requires_decision_and_approved_event_creates_canon_revision(client):
    register_and_login(client)
    novel_id = create_novel(client, "Analysis approval")
    created = client.post(
        f"/api/v1/novels/{novel_id}/ai/analysis-proposals",
        headers=headers(client),
        json={},
    )
    assert created.status_code == 405
    # Proposals are only created from validated structured provider output.
    assert client.get(f"/api/v1/novels/{novel_id}/ai/analysis-proposals").json() == []


def test_reviewed_analysis_event_creates_audited_canon_record(client, monkeypatch):
    register_and_login(client)
    novel_id = create_novel(client, "Analysis review")
    chapter = client.post(
        f"/api/v1/novels/{novel_id}/chapters", headers=headers(client), json={"title": "Event"}
    ).json()
    client.patch(
        f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}",
        headers={**headers(client), "If-Match": '"1"'},
        json={"content_format": "markdown", "markdown": "林渊抵达城门。"},
    )
    version = client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}/versions").json()[0]

    class StructuredProvider:
        def chat(self, messages, *, model, tools=(), response_schema=None):
            return ChatResponse(
                content="分析结果",
                model=model,
                structured_output={
                    "summary": "林渊抵达城门。",
                    "events": [
                        {"title": "抵达城门", "description": "林渊抵达城门。", "story_order": 1}
                    ],
                    "character_states": [],
                    "consistency_warnings": [],
                },
            )

    monkeypatch.setattr(
        "novelforge.ai.analysis_service.create_chat_provider", lambda settings: StructuredProvider()
    )
    analyzed = client.post(
        f"/api/v1/novels/{novel_id}/ai/analysis/{version['id']}", headers=headers(client)
    )
    assert analyzed.status_code == 202
    proposals = client.get(f"/api/v1/novels/{novel_id}/ai/analysis-proposals").json()
    assert len(proposals) == 1 and proposals[0]["status"] == "pending"
    accepted = client.post(
        f"/api/v1/novels/{novel_id}/ai/analysis-proposals/{proposals[0]['id']}/approve",
        headers=headers(client),
        json={"reason": "事件核实"},
    )
    assert accepted.status_code == 200
    events = client.get(f"/api/v1/novels/{novel_id}/events").json()
    assert events[0]["title"] == "抵达城门" and events[0]["canon_status"] == "canon"
    revisions = client.get(
        f"/api/v1/novels/{novel_id}/canon/revisions?entity_type=story_event"
    ).json()
    assert len(revisions) == 1 and revisions[0]["change_reason"] == "事件核实"
