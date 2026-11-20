from test_canon import create_novel, headers, register_and_login


def test_generation_preview_does_not_modify_chapter_until_accept(client):
    register_and_login(client)
    novel_id = create_novel(client, "Generation")
    chapter = client.post(
        f"/api/v1/novels/{novel_id}/chapters", headers=headers(client), json={"title": "Draft"}
    ).json()
    generation = client.post(
        f"/api/v1/novels/{novel_id}/ai/generations",
        headers=headers(client),
        json={"chapter_id": chapter["id"], "instructions": "写一个开场"},
    )
    assert generation.status_code == 202
    session = generation.json()
    assert session["status"] == "succeeded"
    current = client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}")
    assert current.json()["current_version"] == 1
    accepted = client.post(
        f"/api/v1/novels/{novel_id}/ai/generations/{session['id']}/accept",
        headers=headers(client),
        json={"expected_version": 1},
    )
    assert accepted.status_code == 200
    assert accepted.json()["current_version"] == 2


def test_generation_accept_conflict_leaves_manuscript_unchanged(client):
    register_and_login(client)
    novel_id = create_novel(client, "Generation conflict")
    chapter = client.post(
        f"/api/v1/novels/{novel_id}/chapters", headers=headers(client), json={"title": "Draft"}
    ).json()
    generation = client.post(
        f"/api/v1/novels/{novel_id}/ai/generations",
        headers=headers(client),
        json={"chapter_id": chapter["id"], "instructions": "继续"},
    ).json()
    updated = client.patch(
        f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}",
        headers={**headers(client), "If-Match": '"1"'},
        json={"content_format": "markdown", "markdown": "用户正文"},
    )
    assert updated.status_code == 200
    conflict = client.post(
        f"/api/v1/novels/{novel_id}/ai/generations/{generation['id']}/accept",
        headers=headers(client),
        json={"expected_version": 1},
    )
    assert conflict.status_code == 409
    assert (
        client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}").json()["current_version"]
        == 2
    )
