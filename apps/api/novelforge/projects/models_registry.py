"""Import domain models so Alembic sees the complete metadata registry."""

from novelforge.identity.models import AuthSession, User
from novelforge.projects.models import Novel

__all__ = ["AuthSession", "Novel", "User"]
