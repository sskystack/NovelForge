from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from novelforge.canon.models import CanonStatus, Character
from novelforge.database import utc_now

ORIGIN = "http://localhost:5173"
PASSWORD = "correct horse battery staple"


def register_and_login(client: TestClient, email: str = "author@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200


def headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": client.cookies.get("novelforge_csrf", ""),
    }


def create_novel(client: TestClient, title: str) -> str:
    response = client.post("/api/v1/novels", headers=headers(client), json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize(
    ("collection", "create_payload", "update_payload", "name_field"),
    [
        (
            "characters",
            {
                "name": "林渊",
                "aliases": ["阿渊"],
                "summary": "谨慎的外门弟子",
                "personality": {"temperament": "cautious"},
                "background": "出身北境",
                "goals": ["查明星海秘密"],
                "constraints": ["不能暴露身份"],
                "attributes": {"age": 17},
            },
            {"name": "林渊·归来"},
            "name",
        ),
        (
            "locations",
            {"name": "寒山禁地", "description": "封存古代遗迹", "attributes": {"region": "北境"}},
            {"description": "封存星海遗迹"},
            "name",
        ),
        (
            "factions",
            {"name": "青云宗", "description": "北境修行宗门", "attributes": {"rank": "major"}},
            {"description": "以守护北境为宗旨"},
            "name",
        ),
        (
            "world-rules",
            {
                "title": "灵力限制",
                "category": "cultivation",
                "description": "境界限制每次突破的灵力上限。",
                "constraints": {"max_breakthroughs": 1},
            },
            {"title": "灵力与境界限制"},
            "title",
        ),
    ],
)
def test_canon_entity_crud_is_novel_scoped(
    client: TestClient,
    collection: str,
    create_payload: dict,
    update_payload: dict,
    name_field: str,
) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Canon CRUD")
    base = f"/api/v1/novels/{novel_id}/{collection}"

    created = client.post(base, headers=headers(client), json=create_payload)
    assert created.status_code == 201
    entity = created.json()
    entity_id = entity["id"]
    assert entity["novel_id"] == novel_id
    assert entity["canon_status"] == "draft"
    assert entity[name_field] == create_payload[name_field]
    assert entity["created_at"] and entity["updated_at"]

    assert client.get(base).json() == []
    assert client.get(f"{base}?include_non_canon=true").json()[0]["id"] == entity_id
    assert client.get(f"{base}/{entity_id}").json()[name_field] == create_payload[name_field]

    updated = client.patch(f"{base}/{entity_id}", headers=headers(client), json=update_payload)
    assert updated.status_code == 200
    assert updated.json()[name_field] == update_payload.get(name_field, create_payload[name_field])

    deleted = client.delete(f"{base}/{entity_id}", headers=headers(client))
    assert deleted.status_code == 204
    assert client.get(f"{base}/{entity_id}").status_code == 404


def test_child_resource_cannot_cross_novel_path(client: TestClient) -> None:
    register_and_login(client)
    first_novel = create_novel(client, "First")
    second_novel = create_novel(client, "Second")
    created = client.post(
        f"/api/v1/novels/{first_novel}/characters",
        headers=headers(client),
        json={"name": "Private character"},
    )
    character_id = created.json()["id"]

    assert client.get(f"/api/v1/novels/{second_novel}/characters/{character_id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/novels/{second_novel}/characters/{character_id}",
            headers=headers(client),
            json={"name": "Moved"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/novels/{second_novel}/characters/{character_id}", headers=headers(client)
        ).status_code
        == 404
    )


def test_other_user_cannot_read_or_mutate_canon_records(client: TestClient) -> None:
    register_and_login(client, "owner@example.com")
    novel_id = create_novel(client, "Owner novel")
    created = client.post(
        f"/api/v1/novels/{novel_id}/world-rules",
        headers=headers(client),
        json={"title": "Private law", "description": "Only the owner can read this."},
    )
    rule_id = created.json()["id"]

    register_and_login(client, "other@example.com")
    base = f"/api/v1/novels/{novel_id}/world-rules/{rule_id}"
    assert client.get(base).status_code == 404
    assert client.patch(base, headers=headers(client), json={"title": "Taken"}).status_code == 404
    assert client.delete(base, headers=headers(client)).status_code == 404


def test_canon_status_cannot_be_set_without_approval(client: TestClient) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Approval boundary")
    base = f"/api/v1/novels/{novel_id}/characters"

    create_canon = client.post(
        base,
        headers=headers(client),
        json={"name": "Unauthorized canon", "canon_status": "canon"},
    )
    assert create_canon.status_code == 422

    created = client.post(base, headers=headers(client), json={"name": "Draft"})
    update_canon = client.patch(
        f"{base}/{created.json()['id']}",
        headers=headers(client),
        json={"canon_status": "canon"},
    )
    assert update_canon.status_code == 422
    assert update_canon.json()["code"] == "INVALID_REQUEST"

    assert (
        client.patch(
            f"{base}/{created.json()['id']}", headers=headers(client), json={"summary": None}
        ).status_code
        == 422
    )
    assert client.post(base, headers=headers(client), json={"name": "   "}).status_code == 422
    assert (
        client.post(
            f"/api/v1/novels/{novel_id}/world-rules",
            headers=headers(client),
            json={"title": "Rule", "description": "  "},
        ).status_code
        == 422
    )


def test_non_owner_novel_is_hidden_on_canon_routes(client: TestClient) -> None:
    register_and_login(client)
    unknown_id = uuid4()
    response = client.get(f"/api/v1/novels/{unknown_id}/characters")
    assert response.status_code == 404
    assert response.json()["code"] == "NOVEL_NOT_FOUND"


def test_approved_canon_cannot_be_patched_or_deleted_directly(
    client: TestClient,
    db_session: Session,
) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Immutable canon")
    created = client.post(
        f"/api/v1/novels/{novel_id}/characters",
        headers=headers(client),
        json={"name": "Approved"},
    )
    character_id = created.json()["id"]
    character = db_session.get(Character, UUID(character_id))
    assert character is not None
    character.canon_status = CanonStatus.CANON
    character.updated_at = utc_now()
    db_session.commit()

    base = f"/api/v1/novels/{novel_id}/characters/{character_id}"
    patch = client.patch(base, headers=headers(client), json={"name": "Silent edit"})
    assert patch.status_code == 403
    assert patch.json()["code"] == "CANON_REVISION_REQUIRED"
    deleted = client.delete(base, headers=headers(client))
    assert deleted.status_code == 403
    assert deleted.json()["code"] == "CANON_REVISION_REQUIRED"
