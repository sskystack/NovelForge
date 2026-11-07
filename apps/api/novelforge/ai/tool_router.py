from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from novelforge.ai.tools import ToolRegistry
from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User
from novelforge.projects.service import get_novel

router = APIRouter(prefix="/novels/{novel_id}/ai/tools", tags=["ai-tools"])


class ToolExecuteRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    approved_action: bool = False


@router.get("")
def list_tools(
    novel_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    get_novel(db, user, novel_id)
    return ToolRegistry(db, user, novel_id).available()


@router.post("/{tool_name}/execute", status_code=status.HTTP_200_OK)
def execute_tool(
    novel_id: UUID,
    tool_name: str,
    payload: ToolExecuteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> dict:
    get_novel(db, user, novel_id)
    return ToolRegistry(db, user, novel_id).execute(
        tool_name, payload.arguments, approved_action=payload.approved_action
    )
