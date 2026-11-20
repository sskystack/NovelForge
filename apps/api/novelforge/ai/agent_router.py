from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from novelforge.ai.agent_models import AgentRun, AgentStep
from novelforge.ai.agent_service import (
    TERMINAL,
    fingerprint,
    run_detail,
    schedule,
    settings_fingerprint,
)
from novelforge.ai.local_config import effective_settings
from novelforge.database import get_db
from novelforge.errors import Problem
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User
from novelforge.projects.service import get_novel

router = APIRouter(prefix="/novels/{novel_id}/agent/runs", tags=["agent"])


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=20000)
    max_rounds: int = Field(default=6, ge=1, le=20)
    max_tool_calls: int = Field(default=12, ge=1, le=40)
    max_seconds: float = Field(default=60, ge=0.1, le=300)
    max_tokens: int = Field(default=12000, ge=100, le=100000)
    use_mcp: bool = False


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool


def owned_run(db, user, novel_id, run_id):
    get_novel(db, user, novel_id)
    row = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id, AgentRun.novel_id == novel_id, AgentRun.owner_id == user.id
        )
    )
    if row is None:
        raise Problem(404, "AGENT_RUN_NOT_FOUND", "Run not found", "No agent run in this novel.")
    return row


@router.post("", status_code=202)
async def create_run(
    novel_id: UUID,
    payload: RunCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    get_novel(db, user, novel_id)
    if not payload.prompt.strip():
        raise Problem(422, "EMPTY_AGENT_PROMPT", "Prompt required", "Enter a nonempty instruction.")
    if len(request.app.state.agent_tasks) >= 4:
        raise Problem(
            429, "AGENT_CAPACITY", "Agent capacity reached", "Wait for an active run to finish."
        )
    settings = effective_settings(db, user.id, request.app.state.settings)
    row = AgentRun(
        owner_id=user.id,
        novel_id=novel_id,
        prompt=payload.prompt,
        provider=settings.ai_provider,
        model=settings.ai_chat_model,
        limits={
            **payload.model_dump(exclude={"prompt"}),
            "settings_fingerprint": settings_fingerprint(settings),
        },
    )
    db.add(row)
    db.commit()
    result = run_detail(db, row)
    schedule(request.app, row.id)
    return result


@router.get("")
def list_runs(
    novel_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    get_novel(db, user, novel_id)
    return [
        run_detail(db, row)
        for row in db.scalars(
            select(AgentRun)
            .where(AgentRun.owner_id == user.id, AgentRun.novel_id == novel_id)
            .order_by(AgentRun.created_at.desc(), AgentRun.id)
            .limit(100)
        ).all()
    ]


@router.get("/{run_id}")
def get_run(
    novel_id: UUID,
    run_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return run_detail(db, owned_run(db, user, novel_id, run_id))


@router.post("/{run_id}/cancel")
async def cancel_run(
    novel_id: UUID,
    run_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    row = owned_run(db, user, novel_id, run_id)
    if row.status not in TERMINAL:
        row.status, row.updated_at = "cancelled", datetime.now(UTC)
        row.error = (
            "Cancelled by the author. Completed effects are retained and will not be replayed."
        )
        for step in db.scalars(
            select(AgentStep).where(
                AgentStep.run_id == run_id,
                AgentStep.status.in_(["running", "pending", "waiting_approval"]),
            )
        ).all():
            step.status = "cancelled"
        db.commit()
        task = request.app.state.agent_tasks.get(run_id)
        if task:
            task.cancel()
    return run_detail(db, row)


@router.post("/{run_id}/steps/{step_id}/decision", status_code=202)
async def decide_step(
    novel_id: UUID,
    run_id: UUID,
    step_id: UUID,
    payload: Decision,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    row = owned_run(db, user, novel_id, run_id)
    if row.status != "waiting_approval":
        raise Problem(
            409,
            "AGENT_NOT_WAITING",
            "Run not awaiting approval",
            "This run cannot accept a decision.",
        )
    step = db.get(AgentStep, step_id)
    if step is None or step.run_id != run_id or step.arguments_hash != fingerprint(step.arguments):
        raise Problem(
            409,
            "AGENT_ARGUMENTS_CHANGED",
            "Approval target unavailable",
            "This tool request is absent or its immutable arguments changed.",
        )
    if len(request.app.state.agent_tasks) >= 4:
        raise Problem(
            429,
            "AGENT_CAPACITY",
            "Agent capacity reached",
            "Wait for an active run to finish before deciding this step.",
        )
    # Conditional update is a durable compare-and-set. Duplicate clicks and
    # retries cannot create another authorization or another execution.
    result = db.execute(
        update(AgentStep)
        .where(
            AgentStep.id == step_id,
            AgentStep.run_id == run_id,
            AgentStep.status == "waiting_approval",
            AgentStep.decision.is_(None),
        )
        .values(decision=payload.approve, decided_by=user.id, status="pending")
    )
    if result.rowcount != 1:
        db.rollback()
        raise Problem(
            409,
            "AGENT_DECISION_ALREADY_RECORDED",
            "Decision unavailable",
            "This exact step was already decided or does not await approval.",
        )
    row.status, row.updated_at = "queued", datetime.now(UTC)
    db.commit()
    result = run_detail(db, row)
    schedule(request.app, run_id)
    return result
