from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.ai.context import compile_context
from novelforge.ai.factory import create_chat_provider
from novelforge.ai.generation_models import GenerationSession, GenerationStatus, TaskProfile
from novelforge.ai.generation_schemas import GenerationCreate
from novelforge.ai.providers import ChatMessage, ProviderError
from novelforge.errors import Problem
from novelforge.identity.models import User
from novelforge.planning.models import Chapter, ContentFormat
from novelforge.planning.schemas import ChapterUpdate
from novelforge.planning.service import get_chapter, update_chapter
from novelforge.projects.service import get_novel
from novelforge.settings import Settings


def start_generation(
    db: Session, owner: User, novel_id: UUID, payload: GenerationCreate, settings: Settings
) -> GenerationSession:
    get_novel(db, owner, novel_id)
    chapter = None
    if payload.chapter_id is not None:
        chapter = get_chapter(db, owner, novel_id, payload.chapter_id)
    context = {"sections": [], "warnings": []}
    if chapter is not None:
        context = compile_context(
            db,
            novel_id,
            chapter.id,
            token_budget=payload.token_budget,
            query=payload.instructions or None,
        )
    provider = create_chat_provider(settings)
    session = GenerationSession(
        novel_id=novel_id,
        chapter_id=payload.chapter_id,
        created_by=owner.id,
        task_profile=payload.task_profile.value,
        status=GenerationStatus.RUNNING,
        instructions=payload.instructions,
        model=payload.model,
        provider=settings.ai_provider,
        context_snapshot=context,
        expected_version=chapter.current_version if chapter else None,
    )
    db.add(session)
    db.flush()
    prompt = "\n".join(section["text"] for section in context.get("sections", []))
    system_prompts = {
        TaskProfile.OUTLINE: (
            "Draft outline material for the author's review. Do not modify persisted outlines."
        ),
        TaskProfile.WRITING: (
            "Draft chapter prose for the author's review. Do not modify the manuscript."
        ),
        TaskProfile.SUMMARY: (
            "Draft a concise chapter summary for the author's review. "
            "Do not modify chapter metadata."
        ),
        TaskProfile.CRITIQUE: (
            "Critique the chapter and cite concrete issues. Do not modify the manuscript."
        ),
    }
    try:
        response = provider.chat(
            [
                ChatMessage("system", system_prompts[payload.task_profile]),
                ChatMessage("user", f"{payload.instructions}\n{prompt}"),
            ],
            model=payload.model,
        )
        session.output = {
            "content_format": "markdown",
            "markdown": response.content,
            "source_ids": [
                section.get("source_id")
                for section in context.get("sections", [])
                if section.get("source_id")
            ],
            "usage": {
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
            },
        }
        session.status = GenerationStatus.SUCCEEDED
    except ProviderError as error:
        session.status = GenerationStatus.FAILED
        session.error_message = str(error)
    session.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(session)
    return session


def get_generation(
    db: Session, owner: User, novel_id: UUID, generation_id: UUID
) -> GenerationSession:
    get_novel(db, owner, novel_id)
    session = db.scalar(
        select(GenerationSession).where(
            GenerationSession.novel_id == novel_id, GenerationSession.id == generation_id
        )
    )
    if session is None:
        raise Problem(
            404,
            "GENERATION_NOT_FOUND",
            "Generation not found",
            "The generation does not belong to this novel.",
        )
    return session


def cancel_generation(db: Session, session: GenerationSession) -> GenerationSession:
    if session.status in {GenerationStatus.SUCCEEDED, GenerationStatus.ACCEPTED}:
        raise Problem(
            409,
            "GENERATION_ALREADY_FINISHED",
            "Generation already finished",
            "Finished generations cannot be cancelled.",
        )
    session.status = GenerationStatus.CANCELLED
    session.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(session)
    return session


def accept_generation(
    db: Session, owner: User, session: GenerationSession, expected_version: int
) -> Chapter:
    if session.status != GenerationStatus.SUCCEEDED:
        raise Problem(
            409,
            "GENERATION_NOT_ACCEPTABLE",
            "Generation is not ready",
            "Only successful generations can be accepted.",
        )
    if session.chapter_id is None:
        raise Problem(
            422,
            "GENERATION_HAS_NO_CHAPTER",
            "Chapter required",
            "Only chapter generations can be accepted.",
        )
    chapter = get_chapter(db, owner, session.novel_id, session.chapter_id)
    if session.expected_version != expected_version:
        raise Problem(
            409,
            "CHAPTER_VERSION_CONFLICT",
            "Version conflict",
            "The generation was based on a different chapter version.",
        )
    markdown = session.output.get("markdown")
    if not isinstance(markdown, str):
        raise Problem(
            422,
            "GENERATION_OUTPUT_INVALID",
            "Invalid generation output",
            "The generated draft has no markdown content.",
        )
    updated = update_chapter(
        db,
        owner,
        chapter,
        ChapterUpdate(content_format=ContentFormat.MARKDOWN, markdown=markdown),
        expected_version,
    )
    session.status = GenerationStatus.ACCEPTED
    session.updated_at = datetime.now(UTC)
    db.commit()
    return updated
