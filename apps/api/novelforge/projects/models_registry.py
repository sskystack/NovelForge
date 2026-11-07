"""Import domain models so Alembic sees the complete metadata registry."""

from novelforge.ai.analysis_models import ChapterAnalysis
from novelforge.ai.analysis_proposal_models import AnalysisProposal
from novelforge.ai.generation_models import GenerationSession
from novelforge.ai.tool_models import ToolCallAudit
from novelforge.canon.models import (
    CanonProposal,
    CanonRevision,
    Character,
    CharacterState,
    Faction,
    Location,
    Relationship,
    StoryEvent,
    WorldRule,
)
from novelforge.identity.models import AuthSession, User
from novelforge.knowledge.models import KnowledgeChunk, KnowledgeDocument
from novelforge.planning.models import Chapter, ChapterVersion, OutlineNode
from novelforge.projects.models import Novel

__all__ = [
    "AuthSession",
    "Character",
    "CharacterState",
    "CanonProposal",
    "CanonRevision",
    "Chapter",
    "ChapterVersion",
    "Faction",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "ToolCallAudit",
    "GenerationSession",
    "ChapterAnalysis",
    "AnalysisProposal",
    "Location",
    "Novel",
    "OutlineNode",
    "Relationship",
    "StoryEvent",
    "User",
    "WorldRule",
]
