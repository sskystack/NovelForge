from test_canon import create_novel, headers, register_and_login


def test_consistency_check_is_evidence_backed_and_resolvable(client):
    register_and_login(client)
    novel_id = create_novel(client, "Continuity")
    response = client.post(f"/api/v1/novels/{novel_id}/consistency/check", headers=headers(client))
    assert response.status_code == 200 and response.json() == []
    listed = client.get(f"/api/v1/novels/{novel_id}/consistency/issues").json()
    assert listed == []


def test_consistency_detects_and_resolves_unknown_event_source(client):
    register_and_login(client)
    novel_id = create_novel(client, "Evidence")
    client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        headers=headers(client),
        json={"title": "Early chapter", "story_order": 0},
    )
    event = client.post(
        f"/api/v1/novels/{novel_id}/events",
        headers=headers(client),
        json={
            "title": "Arrival",
            "story_order": 1,
        },
    )
    assert event.status_code == 201
    issues = client.post(
        f"/api/v1/novels/{novel_id}/consistency/check", headers=headers(client)
    ).json()
    assert issues and issues[0]["issue_type"] == "chapter_event_order"
    resolved = client.post(
        f"/api/v1/novels/{novel_id}/consistency/issues/{issues[0]['id']}/resolve",
        headers=headers(client),
        json={"status": "dismissed"},
    )
    assert resolved.status_code == 200 and resolved.json()["status"] == "dismissed"
