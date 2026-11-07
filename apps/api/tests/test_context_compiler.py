from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_planning import create_chapter, create_novel, register_and_login

from novelforge.ai.context import compile_context
from novelforge.canon.models import CanonStatus, Character, CharacterState, StoryEvent, WorldRule
from novelforge.planning.models import Chapter


def test_context_compiler_scopes_sources_honors_story_time_and_budget(
    client: TestClient, db_session: Session
) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Compiler")
    chapter_data = create_chapter(client, novel_id, "Current", 1, story_order="20")
    chapter = db_session.get(Chapter, __import__("uuid").UUID(chapter_data["id"]))
    assert chapter is not None
    character = Character(
        novel_id=chapter.novel_id, name="北境旅人", canon_status=CanonStatus.CANON
    )
    other_character = Character(
        novel_id=chapter.novel_id, name="南境旅人", canon_status=CanonStatus.CANON
    )
    db_session.add_all([character, other_character])
    db_session.flush()
    db_session.add_all(
        [
            WorldRule(
                novel_id=chapter.novel_id,
                title="灵力法则",
                description="月光才能恢复灵力。",
                canon_status=CanonStatus.CANON,
            ),
            CharacterState(
                novel_id=chapter.novel_id,
                character_id=character.id,
                story_order=Decimal("10"),
                state={"place": "北境"},
                canon_status=CanonStatus.CANON,
            ),
            CharacterState(
                novel_id=chapter.novel_id,
                character_id=character.id,
                story_order=Decimal("15"),
                valid_to_order=Decimal("18"),
                state={"place": "旧都"},
                canon_status=CanonStatus.CANON,
            ),
            CharacterState(
                novel_id=chapter.novel_id,
                character_id=other_character.id,
                story_order=Decimal("25"),
                state={"place": "未来"},
                canon_status=CanonStatus.CANON,
            ),
            StoryEvent(
                novel_id=chapter.novel_id,
                title="入境",
                description="队伍抵达北境",
                story_order=Decimal("12"),
                canon_status=CanonStatus.CANON,
            ),
        ]
    )
    db_session.commit()

    packet = compile_context(
        db_session, chapter.novel_id, chapter.id, token_budget=150, story_order=Decimal("16")
    )
    kinds = {section["kind"] for section in packet["sections"]}
    assert {"canon_character", "canon_world_rule", "character_state", "story_event"}.issubset(kinds)
    states = [section for section in packet["sections"] if section["kind"] == "character_state"]
    assert len(states) == 1 and "北境" not in states[0]["text"] and "旧都" in states[0]["text"]
    assert packet["estimated_tokens"] <= packet["token_budget"]
    assert packet["model_inference"] == []
    assert all("source_id" in section and "provenance" in section for section in packet["sections"])


def test_context_compile_endpoint_enforces_novel_ownership(client: TestClient) -> None:
    register_and_login(client)
    novel_id = create_novel(client, "Owned")
    foreign_novel = create_novel(client, "Foreign")
    chapter = create_chapter(client, foreign_novel, "Foreign chapter", 1)
    response = client.get(f"/api/v1/novels/{novel_id}/context/compile?chapter_id={chapter['id']}")
    assert response.status_code == 404
