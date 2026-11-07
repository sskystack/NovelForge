from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from novelforge.planning.models import Chapter

ORIGIN = "http://localhost:5173"
PASSWORD = "correct horse battery staple"


def register_and_login(client: TestClient, email: str = "author@example.com") -> None:
    assert (
        client.post(
            "/api/v1/auth/register",
            headers={"Origin": ORIGIN},
            json={"email": email, "password": PASSWORD},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": email, "password": PASSWORD},
        ).status_code
        == 200
    )


def headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": client.cookies.get("novelforge_csrf", ""),
    }


def create_novel(client: TestClient, title: str) -> str:
    response = client.post("/api/v1/novels", headers=headers(client), json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


def create_outline(
    client: TestClient,
    novel_id: str,
    title: str,
    node_type: str = "arc",
    parent_id: str | None = None,
    sort_order: int = 0,
) -> dict:
    response = client.post(
        f"/api/v1/novels/{novel_id}/outlines",
        headers=headers(client),
        json={
            "title": title,
            "node_type": node_type,
            "parent_id": parent_id,
            "sort_order": sort_order,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_chapter(
    client: TestClient,
    novel_id: str,
    title: str,
    number: int | None = None,
    outline_node_id: str | None = None,
    story_order: str | None = None,
) -> dict:
    payload = {"title": title, "chapter_number": number, "outline_node_id": outline_node_id}
    if story_order is not None:
        payload["story_order"] = story_order
    response = client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        headers=headers(client),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_outline_tree_supports_nested_nodes_and_deterministic_order(client: TestClient) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Nested plot")
    book = create_outline(client, novel_id, "Book", "book")
    volume_second = create_outline(client, novel_id, "Volume B", "volume", book["id"], sort_order=2)
    volume_first = create_outline(client, novel_id, "Volume A", "volume", book["id"], sort_order=1)
    arc = create_outline(client, novel_id, "Arc", "arc", volume_first["id"])
    beat = create_outline(client, novel_id, "Beat", "beat", arc["id"])

    response = client.get(f"/api/v1/novels/{novel_id}/outlines")
    assert response.status_code == 200
    tree = response.json()
    assert len(tree) == 1
    assert tree[0]["id"] == book["id"]
    assert [child["id"] for child in tree[0]["children"]] == [
        volume_first["id"],
        volume_second["id"],
    ]
    assert tree[0]["children"][0]["children"][0]["children"][0]["id"] == beat["id"]


def test_outline_update_rejects_cycles_cross_novel_parent_and_bad_range(
    client: TestClient,
) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Cycle check")
    other_novel = create_novel(client, "Other plot")
    root = create_outline(client, novel_id, "Root", "book")
    child = create_outline(client, novel_id, "Child", parent_id=root["id"])
    foreign_root = create_outline(client, other_novel, "Foreign", "book")

    cycle = client.patch(
        f"/api/v1/novels/{novel_id}/outlines/{root['id']}",
        headers=headers(client),
        json={"parent_id": child["id"]},
    )
    assert cycle.status_code == 409
    assert cycle.json()["code"] == "OUTLINE_CYCLE"

    foreign = client.patch(
        f"/api/v1/novels/{novel_id}/outlines/{child['id']}",
        headers=headers(client),
        json={"parent_id": foreign_root["id"]},
    )
    assert foreign.status_code == 404

    invalid_range = client.patch(
        f"/api/v1/novels/{novel_id}/outlines/{child['id']}",
        headers=headers(client),
        json={"planned_start_order": "10", "planned_end_order": "5"},
    )
    assert invalid_range.status_code == 422


def test_outline_reorder_requires_complete_sibling_order_and_is_stable(client: TestClient) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Reorder plot")
    root = create_outline(client, novel_id, "Root", "book")
    first = create_outline(client, novel_id, "First", parent_id=root["id"], sort_order=5)
    second = create_outline(client, novel_id, "Second", parent_id=root["id"], sort_order=8)

    partial = client.post(
        f"/api/v1/novels/{novel_id}/outlines/reorder",
        headers=headers(client),
        json={"parent_id": root["id"], "ordered_node_ids": [first["id"]]},
    )
    assert partial.status_code == 422

    reordered = client.post(
        f"/api/v1/novels/{novel_id}/outlines/reorder",
        headers=headers(client),
        json={"parent_id": root["id"], "ordered_node_ids": [second["id"], first["id"]]},
    )
    assert reordered.status_code == 200
    assert [node["id"] for node in reordered.json()] == [second["id"], first["id"]]
    tree = client.get(f"/api/v1/novels/{novel_id}/outlines").json()
    assert [node["id"] for node in tree[0]["children"]] == [second["id"], first["id"]]


def test_outline_links_must_be_local_and_delete_clears_chapter_links(
    client: TestClient,
    db_session: Session,
) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Outline links")
    other_novel = create_novel(client, "Other novel")
    other_character = client.post(
        f"/api/v1/novels/{other_novel}/characters",
        headers=headers(client),
        json={"name": "Foreign"},
    ).json()

    invalid_link = client.post(
        f"/api/v1/novels/{novel_id}/outlines",
        headers=headers(client),
        json={
            "title": "Foreign link",
            "node_type": "arc",
            "linked_entity_ids": [other_character["id"]],
        },
    )
    assert invalid_link.status_code == 404
    assert invalid_link.json()["code"] == "OUTLINE_LINK_NOT_FOUND"

    chapter_node = create_outline(client, novel_id, "Chapter one", "chapter")
    chapter = create_chapter(client, novel_id, "One", 1, chapter_node["id"])
    deleted = client.delete(
        f"/api/v1/novels/{novel_id}/outlines/{chapter_node['id']}", headers=headers(client)
    )
    assert deleted.status_code == 204
    db_chapter = db_session.get(Chapter, UUID(chapter["id"]))
    assert db_chapter is not None
    db_session.refresh(db_chapter)
    assert db_chapter.outline_node_id is None


def test_chapter_crud_and_pagination_use_deterministic_order(client: TestClient) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Chapter pages")
    second = create_chapter(client, novel_id, "Chapter two", 2, story_order="15")
    first = create_chapter(client, novel_id, "Chapter one", 1, story_order="20")
    unnumbered = create_chapter(client, novel_id, "Unnumbered", None, story_order="3")

    page_one = client.get(f"/api/v1/novels/{novel_id}/chapters?limit=2")
    assert page_one.status_code == 200
    body_one = page_one.json()
    assert [chapter["id"] for chapter in body_one["items"]] == [first["id"], second["id"]]
    assert body_one["next_cursor"]

    page_two = client.get(
        f"/api/v1/novels/{novel_id}/chapters?limit=2&cursor={body_one['next_cursor']}"
    )
    assert [chapter["id"] for chapter in page_two.json()["items"]] == [unnumbered["id"]]
    assert page_two.json()["next_cursor"] is None

    updated = client.patch(
        f"/api/v1/novels/{novel_id}/chapters/{second['id']}",
        headers=headers(client),
        json={"status": "in_progress", "summary": "Entering the mountain."},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"

    assert (
        client.delete(
            f"/api/v1/novels/{novel_id}/chapters/{second['id']}", headers=headers(client)
        ).status_code
        == 204
    )
    assert client.get(f"/api/v1/novels/{novel_id}/chapters/{second['id']}").status_code == 404


def test_chapter_outline_link_requires_chapter_node_in_same_novel(client: TestClient) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Chapter outline link")
    other_novel = create_novel(client, "Foreign outline")
    arc = create_outline(client, novel_id, "An arc", "arc")
    foreign_chapter_node = create_outline(client, other_novel, "Foreign chapter", "chapter")

    non_chapter = client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        headers=headers(client),
        json={"title": "Invalid", "outline_node_id": arc["id"]},
    )
    assert non_chapter.status_code == 422

    foreign = client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        headers=headers(client),
        json={"title": "Foreign", "outline_node_id": foreign_chapter_node["id"]},
    )
    assert foreign.status_code == 404


def test_chapter_and_outline_reads_are_novel_isolated(client: TestClient) -> None:
    register_and_login(client, "owner@example.com")
    novel_id = create_novel(client, "Owner")
    node = create_outline(client, novel_id, "Owner node", "chapter")
    chapter = create_chapter(client, novel_id, "Owner chapter", outline_node_id=node["id"])

    register_and_login(client, "reader@example.com")
    other_novel = create_novel(client, "Reader")
    assert client.get(f"/api/v1/novels/{novel_id}/outlines").status_code == 404
    assert client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}").status_code == 404
    assert client.get(f"/api/v1/novels/{other_novel}/outlines").json() == []


def test_invalid_chapter_cursor_returns_problem_details(client: TestClient) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Cursor validation")
    response = client.get(f"/api/v1/novels/{novel_id}/chapters?cursor=invalid!")
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "INVALID_CURSOR"
