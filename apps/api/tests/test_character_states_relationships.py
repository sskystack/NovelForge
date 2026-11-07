from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from novelforge.canon.models import CanonStatus, CharacterState, Relationship

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


def create_character(client: TestClient, novel_id: str, name: str) -> str:
    response = client.post(
        f"/api/v1/novels/{novel_id}/characters",
        headers=headers(client),
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_event(client: TestClient, novel_id: str, title: str, story_order: str) -> str:
    response = client.post(
        f"/api/v1/novels/{novel_id}/events",
        headers=headers(client),
        json={"title": title, "story_order": story_order},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_state(
    client: TestClient,
    novel_id: str,
    character_id: str,
    story_order: str,
    valid_to_order: str | None,
    state: dict,
    event_id: str | None = None,
) -> str:
    response = client.post(
        f"/api/v1/novels/{novel_id}/characters/{character_id}/states",
        headers=headers(client),
        json={
            "story_order": story_order,
            "valid_to_order": valid_to_order,
            "state": state,
            "source_event_id": event_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def approve_state(db_session: Session, state_id: str) -> None:
    state = db_session.get(CharacterState, UUID(state_id))
    assert state is not None
    state.canon_status = CanonStatus.CANON
    db_session.commit()


def test_character_state_at_order_respects_interval_boundaries_and_flashbacks(
    client: TestClient,
    db_session: Session,
) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Nonlinear timeline")
    character_id = create_character(client, novel_id, "林渊")
    event_past = create_event(client, novel_id, "寒山受伤", "10")
    event_flashback = create_event(client, novel_id, "童年往事", "2")
    event_recovery = create_event(client, novel_id, "伤势痊愈", "20")

    earlier = create_state(
        client,
        novel_id,
        character_id,
        "2",
        "10",
        {"location": "故乡", "age": 8},
        event_flashback,
    )
    injured = create_state(
        client,
        novel_id,
        character_id,
        "10",
        "20",
        {"location": "寒山", "injured": True},
        event_past,
    )
    recovered = create_state(
        client,
        novel_id,
        character_id,
        "20",
        None,
        {"location": "宗门", "injured": False},
        event_recovery,
    )
    for state_id in (earlier, injured, recovered):
        approve_state(db_session, state_id)

    at_9 = client.get(f"/api/v1/novels/{novel_id}/characters/{character_id}/state-at?story_order=9")
    assert at_9.status_code == 200
    assert at_9.json()["state"]["state"]["location"] == "故乡"

    at_10 = client.get(
        f"/api/v1/novels/{novel_id}/characters/{character_id}/state-at?story_order=10"
    )
    assert at_10.json()["state"]["state"]["location"] == "寒山"

    at_20 = client.get(
        f"/api/v1/novels/{novel_id}/characters/{character_id}/state-at?story_order=20"
    )
    assert at_20.json()["state"]["state"]["location"] == "宗门"

    all_states = client.get(f"/api/v1/novels/{novel_id}/character-states?story_order=10")
    assert [entry["state"]["location"] for entry in all_states.json()] == ["寒山"]


def test_character_state_defaults_to_proposed_and_lists_history(client: TestClient) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Proposed state")
    character_id = create_character(client, novel_id, "Ming")
    state_id = create_state(client, novel_id, character_id, "1", None, {"mood": "calm"})

    at_order = client.get(
        f"/api/v1/novels/{novel_id}/characters/{character_id}/state-at?story_order=1"
    )
    assert at_order.status_code == 200
    assert at_order.json()["state"] is None

    history = client.get(f"/api/v1/novels/{novel_id}/characters/{character_id}/states")
    assert history.status_code == 200
    assert history.json()[0]["id"] == state_id
    assert history.json()[0]["canon_status"] == "proposed"


def test_story_event_cannot_be_created_as_canon_without_approval(client: TestClient) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Event approval")
    response = client.post(
        f"/api/v1/novels/{novel_id}/events",
        headers=headers(client),
        json={"title": "Unapproved event", "story_order": "1", "canon_status": "canon"},
    )
    assert response.status_code == 422


def test_event_and_character_state_references_must_match_novel(client: TestClient) -> None:
    register_and_login(client)
    first_novel = create_novel(client, "First timeline")
    second_novel = create_novel(client, "Second timeline")
    character_first = create_character(client, first_novel, "First character")
    character_second = create_character(client, second_novel, "Second character")
    foreign_event = create_event(client, second_novel, "Foreign event", "4")

    foreign_event_state = client.post(
        f"/api/v1/novels/{first_novel}/characters/{character_first}/states",
        headers=headers(client),
        json={
            "story_order": "4",
            "state": {"location": "Elsewhere"},
            "source_event_id": foreign_event,
        },
    )
    assert foreign_event_state.status_code == 404
    assert foreign_event_state.json()["code"] == "STORY_EVENT_NOT_FOUND"

    foreign_character_state = client.post(
        f"/api/v1/novels/{first_novel}/characters/{character_second}/states",
        headers=headers(client),
        json={"story_order": "4", "state": {"location": "Elsewhere"}},
    )
    assert foreign_character_state.status_code == 404


def test_relationship_requires_same_novel_distinct_endpoints_and_valid_interval(
    client: TestClient,
) -> None:
    register_and_login(client)
    first_novel = create_novel(client, "Relationships")
    second_novel = create_novel(client, "Another cast")
    first = create_character(client, first_novel, "A")
    second = create_character(client, first_novel, "B")
    foreign = create_character(client, second_novel, "C")
    base = f"/api/v1/novels/{first_novel}/relationships"

    created = client.post(
        base,
        headers=headers(client),
        json={
            "from_character_id": first,
            "to_character_id": second,
            "relationship_type": "mentor",
            "valid_from_order": "3",
            "valid_to_order": "9",
        },
    )
    assert created.status_code == 201
    assert created.json()["canon_status"] == "draft"
    relationship_id = created.json()["id"]

    assert client.get(f"{base}?include_non_canon=true").json()[0]["id"] == relationship_id
    assert client.get(f"{base}?story_order=2").json() == []

    relationship = client.get(f"{base}?include_non_canon=true").json()[0]
    assert relationship["valid_from_order"] == "3.000000"

    invalid_self = client.post(
        base,
        headers=headers(client),
        json={"from_character_id": first, "to_character_id": first, "relationship_type": "self"},
    )
    assert invalid_self.status_code == 422

    invalid_cross_novel = client.post(
        base,
        headers=headers(client),
        json={"from_character_id": first, "to_character_id": foreign, "relationship_type": "ally"},
    )
    assert invalid_cross_novel.status_code == 404
    assert invalid_cross_novel.json()["code"] == "RELATIONSHIP_ENDPOINT_NOT_FOUND"

    invalid_interval = client.post(
        base,
        headers=headers(client),
        json={
            "from_character_id": first,
            "to_character_id": second,
            "relationship_type": "rival",
            "valid_from_order": "5",
            "valid_to_order": "5",
        },
    )
    assert invalid_interval.status_code == 422


def test_relationship_time_query_uses_half_open_validity(
    client: TestClient, db_session: Session
) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Relationship timeline")
    first = create_character(client, novel_id, "A")
    second = create_character(client, novel_id, "B")
    created = client.post(
        f"/api/v1/novels/{novel_id}/relationships",
        headers=headers(client),
        json={
            "from_character_id": first,
            "to_character_id": second,
            "relationship_type": "ally",
            "valid_from_order": "5",
            "valid_to_order": "10",
        },
    )
    relationship = db_session.get(Relationship, UUID(created.json()["id"]))
    assert relationship is not None
    relationship.canon_status = CanonStatus.CANON
    db_session.commit()

    path = f"/api/v1/novels/{novel_id}/relationships"
    assert len(client.get(f"{path}?story_order=5").json()) == 1
    assert len(client.get(f"{path}?story_order=9.999999").json()) == 1
    assert client.get(f"{path}?story_order=10").json() == []


@pytest.mark.parametrize("endpoint", ["characters/not-a-uuid/state-at", "character-states"])
def test_state_time_query_rejects_missing_or_invalid_order(
    client: TestClient, endpoint: str
) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Invalid state query")
    response = client.get(f"/api/v1/novels/{novel_id}/{endpoint}")
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
