from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from novelforge.database import Base, UTCDateTime


class ToolCallAudit(Base):
    __tablename__ = "tool_call_audits"
    __table_args__ = (
        Index("ix_tool_call_audits_generation", "novel_id", "generation_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    generation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_summary: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
