import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.canon.models import (
    CanonStatus,
    Character,
    CharacterState,
    Faction,
    Location,
    StoryEvent,
    WorldRule,
)
from novelforge.errors import Problem
from novelforge.knowledge.service import search_knowledge
from novelforge.planning.models import Chapter, ChapterVersion, OutlineNode


def _estimate_tokens(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", text))


def _fit_text(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    tokens = re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+|[^\w\s]", text)
    return "".join(tokens[:budget]) if len(tokens) > budget else text


def compile_context(
    db: Session,
    novel_id: UUID,
    chapter_id: UUID,
    *,
    token_budget: int = 4000,
    story_order: Decimal | None = None,
    query: str | None = None,
    include_recent_chapters: int = 3,
) -> dict:
    if token_budget < 100 or token_budget > 100_000:
        raise Problem(
            422,
            "INVALID_CONTEXT_BUDGET",
            "Invalid context budget",
            "token_budget must be between 100 and 100000.",
        )
    chapter = db.scalar(
        select(Chapter).where(Chapter.novel_id == novel_id, Chapter.id == chapter_id)
    )
    if chapter is None:
        raise Problem(
            404,
            "CHAPTER_NOT_FOUND",
            "Chapter not found",
            "The chapter was not found in this novel.",
        )
    version = db.scalar(
        select(ChapterVersion).where(
            ChapterVersion.novel_id == novel_id,
            ChapterVersion.chapter_id == chapter_id,
            ChapterVersion.version_number == chapter.current_version,
        )
    )
    if story_order is None:
        story_order = chapter.story_order

    sections: list[dict] = []
    warnings: list[str] = []

    def add(kind: str, source_id: UUID | None, text: str, provenance: dict | None = None) -> None:
        sections.append(
            {
                "kind": kind,
                "source_id": str(source_id) if source_id else None,
                "text": text,
                "provenance": provenance or {},
            }
        )

    if chapter.outline_node_id:
        outline = db.scalar(
            select(OutlineNode).where(
                OutlineNode.novel_id == novel_id, OutlineNode.id == chapter.outline_node_id
            )
        )
        if outline:
            add("outline", outline.id, f"{outline.title}\n{outline.synopsis}")
    add(
        "current_chapter",
        chapter.id,
        f"{chapter.title}\n{chapter.summary}",
        {"version_number": chapter.current_version},
    )
    if version and version.plain_text:
        add(
            "chapter_version",
            version.id,
            version.plain_text,
            {"version_number": version.version_number},
        )

    for model, kind, fields in (
        (
            Character,
            "canon_character",
            ("name", "summary", "background", "personality", "goals", "constraints", "attributes"),
        ),
        (Location, "canon_location", ("name", "description", "attributes")),
        (Faction, "canon_faction", ("name", "description", "attributes")),
        (WorldRule, "canon_world_rule", ("title", "category", "description", "constraints")),
    ):
        records = db.scalars(
            select(model)
            .where(model.novel_id == novel_id, model.canon_status == CanonStatus.CANON)
            .order_by(model.id)
        ).all()
        for record in records:
            facts = "\n".join(
                f"{field}: {getattr(record, field)}"
                for field in fields
                if getattr(record, field) not in (None, "", [], {})
            )
            add(kind, record.id, facts)

    if story_order is not None:
        state_query = (
            select(CharacterState)
            .where(
                CharacterState.novel_id == novel_id,
                CharacterState.canon_status == CanonStatus.CANON,
                CharacterState.story_order <= story_order,
                (CharacterState.valid_to_order.is_(None))
                | (story_order < CharacterState.valid_to_order),
            )
            .order_by(
                CharacterState.character_id, CharacterState.story_order.desc(), CharacterState.id
            )
        )
        seen: set[UUID] = set()
        for state in db.scalars(state_query).all():
            if state.character_id in seen:
                continue
            seen.add(state.character_id)
            add(
                "character_state",
                state.id,
                str(state.state),
                {
                    "character_id": str(state.character_id),
                    "story_order": str(state.story_order),
                    "source_event_id": str(state.source_event_id)
                    if state.source_event_id
                    else None,
                },
            )
        events = db.scalars(
            select(StoryEvent)
            .where(
                StoryEvent.novel_id == novel_id,
                StoryEvent.canon_status == CanonStatus.CANON,
                StoryEvent.story_order <= story_order,
            )
            .order_by(StoryEvent.story_order.desc())
            .limit(30)
        ).all()
        for event in events:
            add(
                "story_event",
                event.id,
                f"{event.title}\n{event.description}",
                {"story_order": str(event.story_order)},
            )

    if query:
        for hit in search_knowledge(db, novel_id, query, limit=10):
            add(
                "retrieved_prose",
                UUID(hit["chunk_id"]),
                hit["content"],
                {
                    key: hit[key]
                    for key in (
                        "source_type",
                        "source_id",
                        "source_revision",
                        "document_id",
                        "title",
                    )
                },
            )

    # Stable priority order makes output deterministic and keeps primary facts ahead of prose.
    priority = {
        "outline": 0,
        "current_chapter": 1,
        "canon_world_rule": 2,
        "canon_character": 3,
        "canon_location": 4,
        "canon_faction": 5,
        "character_state": 6,
        "story_event": 7,
        "chapter_version": 8,
        "retrieved_prose": 9,
    }
    sections.sort(
        key=lambda section: (priority.get(section["kind"], 99), section["source_id"] or "")
    )
    remaining = token_budget
    output = []
    for section in sections:
        text = _fit_text(section["text"], remaining)
        used = _estimate_tokens(text)
        if not text and section["text"]:
            warnings.append(
                f"Omitted {section['kind']} source {section['source_id']} because the "
                "token budget was exhausted."
            )
            continue
        output.append({**section, "text": text, "token_count": used})
        remaining -= used
    return {
        "novel_id": str(novel_id),
        "chapter_id": str(chapter_id),
        "story_order": str(story_order) if story_order is not None else None,
        "token_budget": token_budget,
        "estimated_tokens": token_budget - remaining,
        "sections": output,
        "warnings": warnings,
        "model_inference": [],
    }
