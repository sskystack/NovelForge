import io
import json
import zipfile

from test_canon import create_novel, headers, register_and_login


def test_export_import_round_trip_remaps_project_and_preserves_chapter(client):
    register_and_login(client)
    novel_id = create_novel(client, "Portable novel")
    character = client.post(
        f"/api/v1/novels/{novel_id}/characters",
        headers=headers(client),
        json={"name": "林渊", "summary": "主角"},
    ).json()
    chapter = client.post(
        f"/api/v1/novels/{novel_id}/chapters", headers=headers(client), json={"title": "Opening"}
    ).json()
    archive = client.get(f"/api/v1/novels/{novel_id}/export")
    assert archive.status_code == 200
    assert archive.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        assert "manifest.json" in bundle.namelist()
        assert "data/knowledge_chunks.json" in bundle.namelist()
        assert json.loads(bundle.read("data/knowledge_chunks.json")) == []
    imported = client.post(
        "/api/v1/novels/import",
        headers={**headers(client), "Content-Type": "application/zip"},
        content=archive.content,
    )
    assert imported.status_code == 201
    imported_id = imported.json()["id"]
    assert imported_id != novel_id
    assert (
        client.get(f"/api/v1/novels/{imported_id}/characters?include_non_canon=true").json()[0][
            "name"
        ]
        == character["name"]
    )
    chapters = client.get(f"/api/v1/novels/{imported_id}/chapters?limit=100").json()["items"]
    assert len(chapters) == 1 and chapters[0]["title"] == chapter["title"]


def test_import_rejects_path_traversal_and_checksum_tampering(client):
    register_and_login(client)
    malicious = io.BytesIO()
    with zipfile.ZipFile(malicious, "w") as bundle:
        bundle.writestr("../escape.json", b"bad")
    response = client.post(
        "/api/v1/novels/import",
        headers={**headers(client), "Content-Type": "application/zip"},
        content=malicious.getvalue(),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_ARCHIVE"
