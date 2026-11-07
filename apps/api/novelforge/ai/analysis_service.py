import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.ai.analysis_models import ChapterAnalysis
from novelforge.ai.analysis_proposal_models import AnalysisProposal
from novelforge.ai.factory import create_chat_provider
from novelforge.ai.providers import ChatMessage, ProviderError
from novelforge.errors import Problem
from novelforge.identity.models import User
from novelforge.knowledge.models import KnowledgeVisibility
from novelforge.knowledge.service import SourceMaterial, ingest_source
from novelforge.planning.models import Chapter, ChapterVersion
from novelforge.projects.service import get_novel
from novelforge.settings import Settings


def analyze_chapter_version(
    db: Session, owner: User, novel_id: UUID, chapter_version_id: UUID, settings: Settings
) -> ChapterAnalysis:
    get_novel(db, owner, novel_id)
    version = db.scalar(
        select(ChapterVersion).where(
            ChapterVersion.novel_id == novel_id, ChapterVersion.id == chapter_version_id
        )
    )
    if version is None:
        raise Problem(
            404,
            "CHAPTER_VERSION_NOT_FOUND",
            "Chapter version not found",
            "The version is not in this novel.",
        )
    existing = db.scalar(
        select(ChapterAnalysis).where(
            ChapterAnalysis.novel_id == novel_id,
            ChapterAnalysis.chapter_version_id == chapter_version_id,
        )
    )
    if existing is not None and existing.status == "succeeded":
        return existing
    analysis = existing or ChapterAnalysis(
        novel_id=novel_id, chapter_id=version.chapter_id, chapter_version_id=version.id
    )
    analysis.status = "running"
    if existing is None:
        db.add(analysis)
    db.flush()
    try:
        provider = create_chat_provider(settings)
        chapter = db.scalar(
            select(Chapter).where(Chapter.novel_id == novel_id, Chapter.id == version.chapter_id)
        )
        if chapter is not None and hasattr(provider, "embed"):
            try:
                ingest_source(
                    db,
                    novel_id,
                    SourceMaterial(
                        source_type="chapter_version",
                        source_id=version.id,
                        title=chapter.title,
                        source_revision=version.version_number,
                        content=version.plain_text,
                        visibility=KnowledgeVisibility.APPROVED,
                    ),
                    provider,
                )
            except Problem as error:
                analysis.warnings = [f"Re-indexing failed: {error.code}"]
        response = provider.chat(
            [
                ChatMessage(
                    "system",
                    "Analyze this chapter. Return a concise summary and only explicit event or "
                    "character-state changes supported by the text. Never claim candidates "
                    "are canonical.",
                ),
                ChatMessage("user", version.plain_text),
            ],
            model="mock-chat",
            response_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "events": {"type": "array", "items": {"type": "object"}},
                    "character_states": {"type": "array", "items": {"type": "object"}},
                    "consistency_warnings": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["summary", "events", "character_states", "consistency_warnings"],
                "additionalProperties": False,
            },
        )
        structured = response.structured_output or {}
        summary = structured.get("summary")
        analysis.summary_candidate = (summary if isinstance(summary, str) else response.content)[
            :50_000
        ]
        candidate_data: dict = {
            key: structured.get(key, []) if isinstance(structured.get(key, []), list) else []
            for key in ("events", "character_states", "consistency_warnings")
        }
        proposal_ids: list[str] = []
        for proposal_type, candidates in (
            ("event", candidate_data["events"]),
            ("character_state", candidate_data["character_states"]),
        ):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                candidate["evidence"] = {
                    "chapter_id": str(version.chapter_id),
                    "chapter_version_id": str(version.id),
                    "version_number": version.version_number,
                }
                fingerprint = hashlib.sha256(
                    json.dumps(candidate, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest()
                proposal = db.scalar(
                    select(AnalysisProposal).where(
                        AnalysisProposal.novel_id == novel_id,
                        AnalysisProposal.chapter_version_id == version.id,
                        AnalysisProposal.proposal_type == proposal_type,
                        AnalysisProposal.fingerprint == fingerprint,
                    )
                )
                if proposal is None:
                    proposal = AnalysisProposal(
                        novel_id=novel_id,
                        chapter_id=version.chapter_id,
                        chapter_version_id=version.id,
                        proposal_type=proposal_type,
                        payload=candidate,
                        evidence=candidate.get("evidence", {}),
                        fingerprint=fingerprint,
                    )
                    db.add(proposal)
                    db.flush()
                proposal_ids.append(str(proposal.id))
        analysis.candidates = candidate_data
        analysis.proposal_ids = proposal_ids
        analysis.summary_candidate = (summary if isinstance(summary, str) else response.content)[
            :50_000
        ]
        analysis.status = "succeeded"
        analysis.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(analysis)
        return analysis
    except ProviderError as error:
        db.rollback()
        analysis = db.get(ChapterAnalysis, analysis.id)
        if analysis is not None:
            analysis.status = "failed"
            analysis.error_message = str(error)
            db.commit()
        raise Problem(
            502,
            "CHAPTER_ANALYSIS_FAILED",
            "Chapter analysis failed",
            "The chapter was not changed.",
        ) from error
