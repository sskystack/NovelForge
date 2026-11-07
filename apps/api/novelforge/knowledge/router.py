from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from novelforge.ai.factory import create_chat_provider
from novelforge.ai.providers import EmbeddingProvider
from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user
from novelforge.identity.models import User
from novelforge.knowledge.models import KnowledgeVisibility
from novelforge.knowledge.service import search_knowledge
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
    settings: Settings = request.app.state.settings
    provider = _embedding_provider(settings)
    return {
        "results": search_knowledge(
            db,
            novel_id,
            query,
            embedding_provider=provider,
            visibility=(
                (KnowledgeVisibility.APPROVED, KnowledgeVisibility.DRAFT)
                if include_drafts
                else (KnowledgeVisibility.APPROVED,)
            ),
            limit=limit,
        )
    }
