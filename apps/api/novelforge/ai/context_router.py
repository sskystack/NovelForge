from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from novelforge.ai.context import compile_context
from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user
from novelforge.identity.models import User
from novelforge.projects.service import get_novel

router = APIRouter(prefix="/novels/{novel_id}/context", tags=["context"])


@router.get("/compile")
def get_context(
    novel_id: UUID,
    chapter_id: UUID,
    token_budget: int = Query(default=4000, ge=100, le=100_000),
    story_order: Decimal | None = Query(default=None, ge=0, max_digits=20, decimal_places=6),
    query: str | None = Query(default=None, max_length=2000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_novel(db, user, novel_id)
    return compile_context(
        db, novel_id, chapter_id, token_budget=token_budget, story_order=story_order, query=query
    )
