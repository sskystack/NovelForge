import base64
import binascii
import json
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from novelforge.canon.models import Character, Faction, Location, StoryEvent, WorldRule
from novelforge.database import utc_now
from novelforge.errors import Problem
from novelforge.identity.models import User
from novelforge.planning.models import Chapter, OutlineNode, OutlineNodeType
from novelforge.planning.schemas import (
    ChapterCreate,
    ChapterPage,
    ChapterUpdate,
    OutlineNodeCreate,
    OutlineNodeRead,
    OutlineNodeUpdate,
)
from novelforge.projects.service import get_novel


def _not_found(code: str, title: str, detail: str) -> Problem:
    return Problem(404, code, title, detail)


def _validate_linked_entities(db: Session, novel_id: UUID, entity_ids: list[UUID]) -> None:
    if not entity_ids:
        return
    models = (Character, Location, Faction, WorldRule, StoryEvent)
    found: set[UUID] = set()
    for model in models:
        found.update(
            db.scalars(
                select(model.id).where(model.novel_id == novel_id, model.id.in_(entity_ids))
            ).all()
        )
    if found != set(entity_ids):
        raise Problem(
            404,
            "OUTLINE_LINK_NOT_FOUND",
            "Linked story record not found",
            "Every linked record must belong to this novel.",
        )


def _validate_parent(db: Session, novel_id: UUID, parent_id: UUID | None) -> OutlineNode | None:
    if parent_id is None:
        return None
    parent = db.scalar(
        select(OutlineNode).where(OutlineNode.id == parent_id, OutlineNode.novel_id == novel_id)
    )
    if parent is None:
        raise _not_found(
            "OUTLINE_PARENT_NOT_FOUND",
            "Outline parent not found",
            "The parent is not in this novel.",
        )
    return parent


def get_outline_node(db: Session, novel_id: UUID, node_id: UUID) -> OutlineNode:
    node = db.scalar(
        select(OutlineNode).where(OutlineNode.novel_id == novel_id, OutlineNode.id == node_id)
    )
    if node is None:
        raise _not_found(
            "OUTLINE_NODE_NOT_FOUND", "Outline node not found", "The node was not found."
        )
    return node


def list_outline_tree(db: Session, owner: User, novel_id: UUID) -> list[OutlineNodeRead]:
    get_novel(db, owner, novel_id)
    nodes = list(
        db.scalars(
            select(OutlineNode)
            .where(OutlineNode.novel_id == novel_id)
            .order_by(
                OutlineNode.parent_id, OutlineNode.sort_order, OutlineNode.title, OutlineNode.id
            )
        ).all()
    )
    children: dict[UUID | None, list[OutlineNode]] = defaultdict(list)
    for node in nodes:
        children[node.parent_id].append(node)

    def tree(node: OutlineNode) -> OutlineNodeRead:
        return OutlineNodeRead(
            **{
                field: getattr(node, field)
                for field in OutlineNodeRead.model_fields
                if field != "children"
            },
            children=[tree(child) for child in children[node.id]],
        )

    return [tree(node) for node in children[None]]


def create_outline_node(
    db: Session,
    owner: User,
    novel_id: UUID,
    payload: OutlineNodeCreate,
) -> OutlineNode:
    get_novel(db, owner, novel_id)
    _validate_parent(db, novel_id, payload.parent_id)
    _validate_linked_entities(db, novel_id, payload.linked_entity_ids)
    node = OutlineNode(novel_id=novel_id, **payload.model_dump())
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def _ensure_no_cycle(
    db: Session,
    novel_id: UUID,
    node_id: UUID,
    parent_id: UUID | None,
) -> None:
    current_id = parent_id
    visited: set[UUID] = set()
    while current_id is not None:
        if current_id == node_id:
            raise Problem(
                409,
                "OUTLINE_CYCLE",
                "Invalid outline hierarchy",
                "An outline node cannot be moved beneath itself or one of its descendants.",
            )
        if current_id in visited:
            raise Problem(
                409,
                "OUTLINE_CYCLE",
                "Invalid outline hierarchy",
                "The existing outline hierarchy contains a cycle.",
            )
        visited.add(current_id)
        current = _validate_parent(db, novel_id, current_id)
        current_id = current.parent_id if current else None


def update_outline_node(
    db: Session,
    owner: User,
    novel_id: UUID,
    node_id: UUID,
    payload: OutlineNodeUpdate,
) -> OutlineNode:
    get_novel(db, owner, novel_id)
    node = get_outline_node(db, novel_id, node_id)
    values = payload.model_dump(exclude_unset=True)
    if "parent_id" in values:
        _validate_parent(db, novel_id, values["parent_id"])
        _ensure_no_cycle(db, novel_id, node_id, values["parent_id"])
    if "linked_entity_ids" in values:
        _validate_linked_entities(db, novel_id, values["linked_entity_ids"])
    start = values.get("planned_start_order", node.planned_start_order)
    end = values.get("planned_end_order", node.planned_end_order)
    if start is not None and end is not None and end < start:
        raise Problem(
            422,
            "INVALID_OUTLINE_RANGE",
            "Invalid planned range",
            "planned_end_order cannot precede planned_start_order.",
        )
    for field, value in values.items():
        setattr(node, field, value)
    db.commit()
    db.refresh(node)
    return node


def delete_outline_node(db: Session, owner: User, novel_id: UUID, node_id: UUID) -> None:
    get_novel(db, owner, novel_id)
    root = get_outline_node(db, novel_id, node_id)
    descendants: set[UUID] = {root.id}
    frontier = [root.id]
    while frontier:
        children = list(
            db.scalars(
                select(OutlineNode.id).where(
                    OutlineNode.novel_id == novel_id,
                    OutlineNode.parent_id.in_(frontier),
                )
            ).all()
        )
        frontier = [child_id for child_id in children if child_id not in descendants]
        descendants.update(frontier)
    db.execute(
        update(Chapter)
        .where(Chapter.novel_id == novel_id, Chapter.outline_node_id.in_(descendants))
        .values(outline_node_id=None, updated_at=utc_now())
    )
    db.delete(root)
    db.commit()


def reorder_outline_nodes(
    db: Session,
    owner: User,
    novel_id: UUID,
    parent_id: UUID | None,
    ordered_node_ids: list[UUID],
) -> list[OutlineNode]:
    get_novel(db, owner, novel_id)
    _validate_parent(db, novel_id, parent_id)
    if len(set(ordered_node_ids)) != len(ordered_node_ids):
        raise Problem(422, "DUPLICATE_OUTLINE_ID", "Invalid reorder", "Node IDs must be unique.")
    parent_filter = (
        OutlineNode.parent_id.is_(None) if parent_id is None else OutlineNode.parent_id == parent_id
    )
    siblings = list(
        db.scalars(select(OutlineNode).where(OutlineNode.novel_id == novel_id, parent_filter)).all()
    )
    sibling_by_id = {node.id: node for node in siblings}
    if set(ordered_node_ids) != set(sibling_by_id):
        raise Problem(
            422,
            "INVALID_OUTLINE_REORDER",
            "Invalid reorder",
            "Reorder must include every sibling node exactly once.",
        )
    for index, node_id in enumerate(ordered_node_ids):
        sibling_by_id[node_id].sort_order = index
        sibling_by_id[node_id].updated_at = utc_now()
    db.commit()
    return [sibling_by_id[node_id] for node_id in ordered_node_ids]


def get_chapter(db: Session, owner: User, novel_id: UUID, chapter_id: UUID) -> Chapter:
    get_novel(db, owner, novel_id)
    chapter = db.scalar(
        select(Chapter).where(Chapter.novel_id == novel_id, Chapter.id == chapter_id)
    )
    if chapter is None:
        raise _not_found("CHAPTER_NOT_FOUND", "Chapter not found", "The chapter was not found.")
    return chapter


def _validate_chapter_outline(
    db: Session,
    novel_id: UUID,
    outline_node_id: UUID | None,
) -> None:
    if outline_node_id is None:
        return
    node = db.scalar(
        select(OutlineNode).where(
            OutlineNode.novel_id == novel_id,
            OutlineNode.id == outline_node_id,
        )
    )
    if node is None:
        raise _not_found(
            "OUTLINE_NODE_NOT_FOUND", "Outline node not found", "The outline node was not found."
        )
    if node.node_type != OutlineNodeType.CHAPTER:
        raise Problem(
            422,
            "OUTLINE_NODE_NOT_CHAPTER",
            "Invalid chapter outline link",
            "A chapter can only link to an outline node of type chapter.",
        )


def create_chapter(
    db: Session,
    owner: User,
    novel_id: UUID,
    payload: ChapterCreate,
) -> Chapter:
    get_novel(db, owner, novel_id)
    _validate_chapter_outline(db, novel_id, payload.outline_node_id)
    chapter = Chapter(novel_id=novel_id, **payload.model_dump())
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


def update_chapter(
    db: Session,
    chapter: Chapter,
    payload: ChapterUpdate,
) -> Chapter:
    values = payload.model_dump(exclude_unset=True)
    if "outline_node_id" in values:
        _validate_chapter_outline(db, chapter.novel_id, values["outline_node_id"])
    for field, value in values.items():
        setattr(chapter, field, value)
    db.commit()
    db.refresh(chapter)
    return chapter


def delete_chapter(db: Session, chapter: Chapter) -> None:
    db.delete(chapter)
    db.commit()


def _encode_offset(offset: int) -> str:
    raw = json.dumps({"offset": offset}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        offset = json.loads(raw)["offset"]
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError) as error:
        raise Problem(
            400, "INVALID_CURSOR", "Invalid cursor", "The chapter cursor is invalid."
        ) from error
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise Problem(400, "INVALID_CURSOR", "Invalid cursor", "The chapter cursor is invalid.")
    return offset


def list_chapters(
    db: Session,
    owner: User,
    novel_id: UUID,
    limit: int,
    cursor: str | None,
) -> ChapterPage:
    get_novel(db, owner, novel_id)
    offset = _decode_offset(cursor)
    statement = (
        select(Chapter)
        .where(Chapter.novel_id == novel_id)
        .order_by(
            Chapter.chapter_number.is_(None),
            Chapter.chapter_number,
            Chapter.story_order.is_(None),
            Chapter.story_order,
            Chapter.id,
        )
        .offset(offset)
        .limit(limit + 1)
    )
    rows = list(db.scalars(statement).all())
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = _encode_offset(offset + len(items)) if has_more else None
    return ChapterPage(items=items, next_cursor=next_cursor)
