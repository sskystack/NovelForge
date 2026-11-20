from uuid import uuid4

import pytest

from novelforge.ai.tools import ToolRegistry
from novelforge.canon.models import Character
from novelforge.errors import Problem
from novelforge.identity.models import User
from novelforge.identity.security import password_hasher
from novelforge.projects.models import Novel


def setup_novel(db_session):
    user = User(
        email=f"tool-{uuid4()}@example.com",
        password_hash=password_hasher.hash("correct horse battery staple"),
    )
    db_session.add(user)
    db_session.flush()
    novel = Novel(owner_user_id=user.id, title="Tools")
    db_session.add(novel)
    db_session.commit()
    return user, novel


def test_tool_registry_reads_only_canon_and_audits(db_session):
    user, novel = setup_novel(db_session)
    db_session.add_all(
        [
            Character(novel_id=novel.id, name="Canon", canon_status="canon"),
            Character(novel_id=novel.id, name="Draft", canon_status="draft"),
        ]
    )
    db_session.commit()
    registry = ToolRegistry(db_session, user, novel.id)
    result = registry.execute("read_characters", {"query": "Canon"})
    assert [item["name"] for item in result["items"]] == ["Canon"]
    assert (
        db_session.query(
            __import__("novelforge.ai.tool_models", fromlist=["ToolCallAudit"]).ToolCallAudit
        ).count()
        == 1
    )


def test_tool_registry_rejects_invalid_and_unapproved_canon_write(db_session):
    user, novel = setup_novel(db_session)
    registry = ToolRegistry(db_session, user, novel.id, max_calls=2)
    with pytest.raises(Problem) as rejected:
        registry.execute(
            "propose_canon", {"entity_type": "character", "proposed_data": {"name": "x"}}
        )
    assert rejected.value.code == "TOOL_APPROVAL_REQUIRED"
    with pytest.raises(Problem) as invalid:
        registry.execute("read_characters", {"query": "x", "limit": 999})
    assert invalid.value.code == "INVALID_TOOL_ARGUMENTS"
