import hashlib
import secrets
from datetime import timedelta

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.database import utc_now
from novelforge.identity.models import AuthSession, User

password_hasher = PasswordHash.recommended()


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User, ttl_hours: int) -> tuple[str, str, AuthSession]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    session = AuthSession(
        user=user,
        token_hash=hash_session_token(token),
        expires_at=utc_now() + timedelta(hours=ttl_hours),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, csrf_token, session


def authenticate(db: Session, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not password_hasher.verify(password, user.password_hash):
        return None
    return user
