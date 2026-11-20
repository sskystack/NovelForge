from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.ai.factory import create_chat_provider
from novelforge.ai.local_config import effective_settings
from novelforge.ai.providers import EmbeddingProvider
from novelforge.database import get_db
from novelforge.errors import Problem
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User
from novelforge.knowledge.models import KnowledgeDocument, KnowledgeVisibility
from novelforge.knowledge.service import SourceMaterial, ingest_source, search_knowledge
from novelforge.projects.service import get_novel
from novelforge.settings import Settings

router = APIRouter(prefix="/novels/{novel_id}/knowledge", tags=["knowledge"])


def _embedding_provider(settings: Settings) -> EmbeddingProvider:
    return create_chat_provider(settings)  # Both configured providers implement embed.


@router.get("/search")
def get_knowledge_search(
    novel_id: UUID,
    request: Request,
    query: str = Query(min_length=1, max_length=2000),
    limit: int = Query(default=10, ge=1, le=50),
    include_drafts: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_novel(db, user, novel_id)
    settings = effective_settings(db, user.id, request.app.state.settings)
    provider = _embedding_provider(settings)
    return {
        "results": search_knowledge(
            db,
            novel_id,
            query,
            embedding_provider=provider,
            embedding_model=settings.ai_embedding_model,
            visibility=(
                (KnowledgeVisibility.APPROVED, KnowledgeVisibility.DRAFT)
                if include_drafts
                else (KnowledgeVisibility.APPROVED,)
            ),
            limit=limit,
        )
    }


class KnowledgeIngest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=200000)
    source_id: UUID | None = None
    source_revision: int = Field(default=1, ge=1)
    visibility: Literal["approved", "draft", "private"] = "approved"


def document_json(document):
    return {
        "id": str(document.id),
        "title": document.title,
        "source_id": str(document.source_id) if document.source_id else None,
        "source_revision": document.source_revision,
        "visibility": document.visibility,
        "status": document.status,
        "error_message": document.error_message,
    }


@router.get("/documents")
def list_documents(
    novel_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    get_novel(db, user, novel_id)
    return [
        document_json(doc)
        for doc in db.scalars(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.novel_id == novel_id)
            .order_by(KnowledgeDocument.created_at.desc())
            .limit(500)
        ).all()
    ]


@router.post("/documents", status_code=201)
def ingest_document(
    novel_id: UUID,
    payload: KnowledgeIngest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    get_novel(db, user, novel_id)
    settings = effective_settings(db, user.id, request.app.state.settings)
    return document_json(
        ingest_source(
            db,
            novel_id,
            SourceMaterial(
                "manual",
                payload.source_id or uuid4(),
                payload.title,
                payload.source_revision,
                payload.content,
                KnowledgeVisibility(payload.visibility),
            ),
            _embedding_provider(settings),
            embedding_model=settings.ai_embedding_model,
        )
    )


@router.delete("/documents/{document_id}", status_code=204)
def remove_document(
    novel_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    get_novel(db, user, novel_id)
    row = db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id, KnowledgeDocument.novel_id == novel_id
        )
    )
    if row is None:
        raise Problem(
            404, "KNOWLEDGE_DOCUMENT_NOT_FOUND", "Document not found", "No document in this novel."
        )
    db.delete(row)
    db.commit()
