from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from novelforge.database import Base, UTCDateTime


class IssueStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    FALSE_POSITIVE = "false_positive"


class ConsistencyIssue(Base):
    __tablename__ = "consistency_issues"
    __table_args__ = (
        UniqueConstraint("novel_id", "fingerprint", name="uq_consistency_issue_fingerprint"),
        Index("ix_consistency_issues_novel_status", "novel_id", "status", "severity"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    issue_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[IssueStatus] = mapped_column(
        String(30), nullable=False, default=IssueStatus.OPEN
    )
    resolved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
