"""Import domain models so Alembic sees the complete metadata registry."""

from novelforge.canon.models import Character, Faction, Location, WorldRule
from novelforge.identity.models import AuthSession, User
from novelforge.projects.models import Novel

__all__ = [
    "AuthSession",
    "Character",
    "Faction",
    "Location",
    "Novel",
    "User",
    "WorldRule",
]
