from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_canon import create_novel, headers, register_and_login

from novelforge.canon.models import CanonProposal, CanonRevision, Character, ProposalStatus


def test_proposal_approval_revision_restore_and_rejection(
    client: TestClient, db_session: Session
) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Canon revisions")
    base = f"/api/v1/novels/{novel_id}/canon"

    create = client.post(
        f"/api/v1/novels/{novel_id}/characters",
        headers=headers(client),
        json={"name": "原名", "summary": "初始设定"},
    )
    character_id = create.json()["id"]
    proposal = client.post(
        f"{base}/proposals",
        headers=headers(client),
        json={
            "entity_type": "character",
            "entity_id": character_id,
            "proposed_data": {"name": "新名"},
            "rationale": "剧情揭示了真实身份",
        },
    )
    assert proposal.status_code == 201
    proposal_id = proposal.json()["id"]
    assert client.get(f"{base}/revisions?entity_id={character_id}").json() == []

    approved = client.post(
        f"{base}/proposals/{proposal_id}/approve",
        headers=headers(client),
        json={"reason": "确认身份反转"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by"]
    assert (
        client.get(
            f"/api/v1/novels/{novel_id}/characters/{character_id}?include_non_canon=true"
        ).json()["canon_status"]
        == "canon"
    )

    history = client.get(f"{base}/revisions?entity_id={character_id}")
    assert history.status_code == 200
    first_revision = history.json()[0]
    assert first_revision["revision_number"] == 1
    assert first_revision["before_data"]["name"] == "原名"
    assert first_revision["after_data"]["name"] == "新名"
    assert first_revision["change_reason"] == "确认身份反转"
    assert first_revision["source_proposal_id"] == proposal_id

    rejected_proposal = client.post(
        f"{base}/proposals",
        headers=headers(client),
        json={
            "entity_type": "character",
            "entity_id": character_id,
            "proposed_data": {"name": "被拒绝的名字"},
            "rationale": "待核实",
        },
    )
    rejected = client.post(
        f"{base}/proposals/{rejected_proposal.json()['id']}/reject",
        headers=headers(client),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    character = db_session.get(Character, UUID(character_id))
    assert character is not None and character.name == "新名"
    assert len(client.get(f"{base}/revisions?entity_id={character_id}").json()) == 1

    later_proposal = client.post(
        f"{base}/proposals",
        headers=headers(client),
        json={
            "entity_type": "character",
            "entity_id": character_id,
            "proposed_data": {"name": "后来版本"},
        },
    )
    later_approval = client.post(
        f"{base}/proposals/{later_proposal.json()['id']}/approve",
        headers=headers(client),
        json={},
    )
    assert later_approval.status_code == 200

    restored = client.post(
        f"{base}/revisions/restore",
        headers=headers(client),
        json={"revision_id": first_revision["id"], "reason": "恢复首次批准版本"},
    )
    assert restored.status_code == 200
    assert restored.json()["revision_number"] == 3
    assert restored.json()["before_data"]["name"] == "后来版本"
    assert restored.json()["after_data"]["name"] == "新名"
    assert len(client.get(f"{base}/revisions?entity_id={character_id}").json()) == 3

    proposal_row = db_session.get(CanonProposal, UUID(rejected_proposal.json()["id"]))
    assert proposal_row is not None and proposal_row.status == ProposalStatus.REJECTED
    revision_rows = db_session.query(CanonRevision).filter_by(novel_id=UUID(novel_id)).all()
    assert len(revision_rows) == 3


def test_proposal_and_revision_access_is_novel_scoped(client: TestClient) -> None:
    register_and_login(client)
    first_novel = create_novel(client, "Revision owner")
    second_novel = create_novel(client, "Other novel")
    created = client.post(
        f"/api/v1/novels/{first_novel}/characters",
        headers=headers(client),
        json={"name": "Private"},
    )
    proposal = client.post(
        f"/api/v1/novels/{first_novel}/canon/proposals",
        headers=headers(client),
        json={
            "entity_type": "character",
            "entity_id": created.json()["id"],
            "proposed_data": {"name": "Changed"},
        },
    )
    path = f"/api/v1/novels/{second_novel}/canon"
    assert client.get(f"{path}/proposals").json() == []
    assert client.get(f"{path}/revisions?entity_id={created.json()['id']}").json() == []
    assert (
        client.post(
            f"{path}/proposals/{proposal.json()['id']}/approve",
            headers=headers(client),
            json={},
        ).status_code
        == 404
    )


def test_proposal_cannot_reference_character_from_another_novel(client: TestClient) -> None:
    register_and_login(client)
    first_novel = create_novel(client, "Character home")
    second_novel = create_novel(client, "Proposal home")
    created = client.post(
        f"/api/v1/novels/{first_novel}/characters",
        headers=headers(client),
        json={"name": "Elsewhere"},
    )
    response = client.post(
        f"/api/v1/novels/{second_novel}/canon/proposals",
        headers=headers(client),
        json={
            "entity_type": "character",
            "entity_id": created.json()["id"],
            "proposed_data": {"name": "Cross novel"},
        },
    )
    assert response.status_code == 404
