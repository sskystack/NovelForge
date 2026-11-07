"""Import domain models so Alembic sees the complete metadata registry."""

from novelforge.canon.models import (
    Character,
    CharacterState,
    Faction,
    Location,
    Relationship,
    StoryEvent,
    WorldRule,
)
from novelforge.identity.models import AuthSession, User
from novelforge.planning.models import Chapter, OutlineNode
from novelforge.projects.models import Novel

__all__ = [
    "AuthSession",
    "Character",
    "CharacterState",
    "Chapter",
    "Faction",
    "Location",
    "Novel",
    "OutlineNode",
    "Relationship",
    "StoryEvent",
    "User",
    "WorldRule",
]
