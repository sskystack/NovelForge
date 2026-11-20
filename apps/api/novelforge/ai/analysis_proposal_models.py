from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from novelforge.database import Base, UTCDateTime


class AnalysisProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AnalysisProposal(Base):
    __tablename__ = "analysis_proposals"
    __table_args__ = (
        UniqueConstraint(
            "novel_id",
            "chapter_version_id",
            "proposal_type",
            "fingerprint",
            name="uq_analysis_proposal_fingerprint",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[UUID] = mapped_column(nullable=False)
    chapter_version_id: Mapped[UUID] = mapped_column(nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    evidence: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[AnalysisProposalStatus] = mapped_column(
        String(20), nullable=False, default=AnalysisProposalStatus.PENDING
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
