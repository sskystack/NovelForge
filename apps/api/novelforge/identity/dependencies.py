import secrets

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.database import get_db, utc_now
from novelforge.errors import Problem
from novelforge.identity.models import AuthSession, User
from novelforge.identity.security import hash_session_token
from novelforge.settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    authorization = request.headers.get("authorization", "")
    bearer_token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    token = bearer_token or request.cookies.get(settings.session_cookie_name)
    if not token:
        raise Problem(401, "AUTHENTICATION_REQUIRED", "Authentication required", "Please log in.")

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_session_token(token),
            AuthSession.expires_at > utc_now(),
        )
    )
    if session is None:
        raise Problem(401, "INVALID_SESSION", "Authentication required", "Please log in again.")
    user = db.get(User, session.user_id)
    if user is None:
        raise Problem(401, "INVALID_SESSION", "Authentication required", "Please log in again.")
    return user


def require_csrf(request: Request, settings: Settings = Depends(get_settings)) -> None:
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        return
    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    header_token = request.headers.get("X-CSRF-Token", "")
    if (
        not cookie_token
        or not header_token
        or not secrets.compare_digest(cookie_token, header_token)
    ):
        raise Problem(
            403,
            "CSRF_VALIDATION_FAILED",
            "Request rejected",
            "CSRF token is missing or invalid.",
        )


def require_allowed_origin(request: Request, settings: Settings = Depends(get_settings)) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.allowed_origins:
        raise Problem(
            403, "ORIGIN_NOT_ALLOWED", "Request rejected", "Request origin is not allowed."
        )
