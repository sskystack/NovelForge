import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from novelforge.ai.tool_schemas import (
    CanonProposalInput,
    ChapterSearch,
    CharacterLookup,
    OutlineDraft,
    OutlineLookup,
    SummaryDraft,
    TimelineLookup,
    WorldbuildingLookup,
)
from novelforge.canon.models import (
    CanonStatus,
    Character,
    Faction,
    Location,
    StoryEvent,
    WorldRule,
)
from novelforge.canon.revision_service import create_proposal
from novelforge.errors import Problem
from novelforge.identity.models import User
from novelforge.knowledge.models import KnowledgeVisibility
from novelforge.knowledge.service import search_knowledge
from novelforge.planning.models import Chapter, OutlineNode
from novelforge.projects.service import get_novel


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    permission: str
    input_schema: type[BaseModel]
    handler: Callable
    timeout_seconds: float = 2.0


class ToolRegistry:
    def __init__(
        self,
        db: Session,
        owner: User,
        novel_id: UUID,
        *,
        generation_id: UUID | None = None,
        max_calls: int = 20,
        timeout_seconds: float = 2.0,
    ):
        self.db = db
        self.owner = owner
        self.novel_id = novel_id
        self.generation_id = generation_id
        self.max_calls = max_calls
        self.timeout_seconds = timeout_seconds
        self.call_count = 0
        self.definitions = self._definitions()

    def _definitions(self) -> dict[str, ToolDefinition]:
        return {
            "read_characters": ToolDefinition(
                "read_characters", "read", CharacterLookup, self._read_characters
            ),
            "read_worldbuilding": ToolDefinition(
                "read_worldbuilding", "read", WorldbuildingLookup, self._read_worldbuilding
            ),
            "read_timeline": ToolDefinition(
                "read_timeline", "read", TimelineLookup, self._read_timeline
            ),
            "read_outline": ToolDefinition(
                "read_outline", "read", OutlineLookup, self._read_outline
            ),
            "search_chapters": ToolDefinition(
                "search_chapters", "read", ChapterSearch, self._search_chapters
            ),
            "draft_outline": ToolDefinition(
                "draft_outline", "draft", OutlineDraft, self._draft_outline
            ),
            "draft_summary": ToolDefinition(
                "draft_summary", "draft", SummaryDraft, self._draft_summary
            ),
            "propose_canon": ToolDefinition(
                "propose_canon", "propose", CanonProposalInput, self._propose_canon
            ),
        }

    def available(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "permission": tool.permission,
                "input_schema": tool.input_schema.model_json_schema(),
            }
            for tool in self.definitions.values()
        ]

    def execute(
        self, name: str, arguments: dict[str, Any], *, approved_action: bool = False
    ) -> dict:
        self.call_count += 1
        tool = self.definitions.get(name)
        status = "failed"
        started = time.monotonic()
        result: dict = {}
        try:
            if self.call_count > self.max_calls:
                raise Problem(
                    429,
                    "TOOL_CALL_LIMIT",
                    "Tool call limit reached",
                    "The generation exceeded its tool call limit.",
                )
            if tool is None:
                raise Problem(
                    404, "TOOL_NOT_FOUND", "Tool not found", "This tool is not registered."
                )
            if tool.permission == "propose" and not approved_action:
                raise Problem(
                    403,
                    "TOOL_APPROVAL_REQUIRED",
                    "Approval required",
                    "Canon changes require explicit user approval.",
                )
            get_novel(self.db, self.owner, self.novel_id)
            try:
                payload = tool.input_schema.model_validate(arguments)
            except ValidationError as error:
                raise Problem(
                    422, "INVALID_TOOL_ARGUMENTS", "Invalid tool arguments", str(error)
                ) from error
            result = tool.handler(payload)
            status = "succeeded"
            return result
        finally:
            self._audit(name, status, int((time.monotonic() - started) * 1000), arguments)

    def _audit(self, name: str, status: str, duration_ms: int, arguments: dict) -> None:
        try:
            from novelforge.ai.tool_models import ToolCallAudit

            self.db.add(
                ToolCallAudit(
                    novel_id=self.novel_id,
                    generation_id=self.generation_id,
                    tool_name=name,
                    status=status,
                    duration_ms=duration_ms,
                    input_summary=json.dumps(arguments, ensure_ascii=False)[:2000],
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _read_characters(self, payload: CharacterLookup) -> dict:
        statement = select(Character).where(
            Character.novel_id == self.novel_id, Character.canon_status == CanonStatus.CANON
        )
        statement = statement.where(
            or_(
                Character.name.ilike(f"%{payload.query}%"),
                Character.summary.ilike(f"%{payload.query}%"),
            )
        )
        rows = self.db.scalars(
            statement.order_by(Character.name, Character.id).limit(payload.limit)
        ).all()
        return {
            "items": [{"id": str(row.id), "name": row.name, "summary": row.summary} for row in rows]
        }

    def _read_worldbuilding(self, payload: WorldbuildingLookup) -> dict:
        model = {
            "character": Character,
            "location": Location,
            "faction": Faction,
            "world_rule": WorldRule,
        }[payload.entity_type]
        statement = select(model).where(
            model.novel_id == self.novel_id, model.canon_status == CanonStatus.CANON
        )
        if payload.query != "*":
            field = model.name if payload.entity_type != "world_rule" else model.title
            statement = statement.where(
                or_(field.ilike(f"%{payload.query}%"), model.summary.ilike(f"%{payload.query}%"))
                if payload.entity_type == "character"
                else field.ilike(f"%{payload.query}%")
            )
        rows = self.db.scalars(statement.order_by(model.id).limit(payload.limit)).all()
        return {
            "items": [
                {
                    "id": str(row.id),
                    "name": getattr(row, "name", getattr(row, "title", "")),
                    "description": getattr(row, "description", getattr(row, "summary", "")),
                }
                for row in rows
            ]
        }

    def _read_timeline(self, payload: TimelineLookup) -> dict:
        statement = select(StoryEvent).where(
            StoryEvent.novel_id == self.novel_id, StoryEvent.canon_status == CanonStatus.CANON
        )
        if payload.story_order_from is not None:
            statement = statement.where(StoryEvent.story_order >= payload.story_order_from)
        if payload.story_order_to is not None:
            statement = statement.where(StoryEvent.story_order <= payload.story_order_to)
        if payload.query:
            statement = statement.where(
                or_(
                    StoryEvent.title.ilike(f"%{payload.query}%"),
                    StoryEvent.description.ilike(f"%{payload.query}%"),
                )
            )
        rows = self.db.scalars(
            statement.order_by(StoryEvent.story_order, StoryEvent.id).limit(payload.limit)
        ).all()
        return {
            "items": [
                {
                    "id": str(row.id),
                    "title": row.title,
                    "description": row.description,
                    "story_order": str(row.story_order),
                }
                for row in rows
            ]
        }

    def _read_outline(self, payload: OutlineLookup) -> dict:
        statement = select(OutlineNode).where(OutlineNode.novel_id == self.novel_id)
        if payload.query:
            statement = statement.where(
                or_(
                    OutlineNode.title.ilike(f"%{payload.query}%"),
                    OutlineNode.synopsis.ilike(f"%{payload.query}%"),
                )
            )
        rows = self.db.scalars(
            statement.order_by(OutlineNode.parent_id, OutlineNode.sort_order, OutlineNode.id).limit(
                payload.limit
            )
        ).all()
        return {
            "items": [
                {
                    "id": str(row.id),
                    "parent_id": str(row.parent_id) if row.parent_id else None,
                    "type": row.node_type.value,
                    "title": row.title,
                    "synopsis": row.synopsis,
                }
                for row in rows
            ]
        }

    def _search_chapters(self, payload: ChapterSearch) -> dict:
        hits = search_knowledge(
            self.db,
            self.novel_id,
            payload.query,
            visibility=(KnowledgeVisibility.APPROVED,),
            limit=payload.limit,
        )
        return {"items": hits}

    def _draft_outline(self, payload: OutlineDraft) -> dict:
        if (
            payload.parent_id
            and self.db.scalar(
                select(OutlineNode.id).where(
                    OutlineNode.novel_id == self.novel_id, OutlineNode.id == payload.parent_id
                )
            )
            is None
        ):
            raise Problem(
                404,
                "OUTLINE_PARENT_NOT_FOUND",
                "Outline parent not found",
                "The parent is not in this novel.",
            )
        return {
            "kind": "outline",
            "parent_id": str(payload.parent_id) if payload.parent_id else None,
            "node_type": payload.node_type,
            "title": payload.title,
            "synopsis": payload.synopsis,
            "sort_order": payload.sort_order,
        }

    def _draft_summary(self, payload: SummaryDraft) -> dict:
        chapter = self.db.scalar(
            select(Chapter).where(
                Chapter.novel_id == self.novel_id, Chapter.id == payload.chapter_id
            )
        )
        if chapter is None:
            raise Problem(
                404, "CHAPTER_NOT_FOUND", "Chapter not found", "The chapter is not in this novel."
            )
        return {"kind": "summary", "chapter_id": str(chapter.id), "summary": payload.summary}

    def _propose_canon(self, payload: CanonProposalInput) -> dict:
        proposal = create_proposal(
            self.db,
            self.novel_id,
            self.owner,
            payload.entity_type,
            payload.entity_id,
            payload.proposed_data,
            payload.rationale,
        )
        return {"proposal_id": str(proposal.id), "status": proposal.status.value}
