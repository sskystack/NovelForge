from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from novelforge.database import get_db
from novelforge.errors import Problem
from novelforge.identity.dependencies import (
    get_current_user,
    get_settings,
    require_allowed_origin,
    require_csrf,
)
from novelforge.identity.models import AuthSession, User
from novelforge.identity.schemas import UserCreate, UserLogin, UserRead
from novelforge.identity.security import (
    authenticate,
    create_session,
    hash_session_token,
    password_hasher,
)
from novelforge.settings import Settings

router = APIRouter(prefix="/auth", tags=["identity"])


def set_session_cookies(
    response: Response,
    settings: Settings,
    session_token: str,
    csrf_token: str,
) -> None:
    max_age = settings.session_ttl_hours * 60 * 60
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite.lower(),
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite.lower(),
        path="/",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    for cookie_name, http_only in (
        (settings.session_cookie_name, True),
        (settings.csrf_cookie_name, False),
    ):
        response.delete_cookie(
            cookie_name,
            path="/",
            secure=settings.session_cookie_secure,
            httponly=http_only,
            samesite=settings.session_cookie_samesite.lower(),
        )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
    _origin: None = Depends(require_allowed_origin),
) -> User:
    user = User(
        email=str(payload.email).strip().lower(),
        password_hash=password_hasher.hash(payload.password),
        display_name=payload.display_name.strip(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise Problem(
            409,
            "EMAIL_ALREADY_EXISTS",
            "Email already registered",
            "An account with this email already exists.",
        ) from error
    db.refresh(user)
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/login", response_model=UserRead)
def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _origin: None = Depends(require_allowed_origin),
) -> User:
    user = authenticate(db, str(payload.email), payload.password)
    if user is None:
        raise Problem(401, "INVALID_CREDENTIALS", "Login failed", "Email or password is incorrect.")

    old_token = request.cookies.get(settings.session_cookie_name)
    if old_token:
        db.execute(
            delete(AuthSession).where(AuthSession.token_hash == hash_session_token(old_token))
        )
        db.commit()
    session_token, csrf_token, _session = create_session(db, user, settings.session_ttl_hours)
    set_session_cookies(response, settings, session_token, csrf_token)
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _origin: None = Depends(require_allowed_origin),
    _csrf: None = Depends(require_csrf),
) -> Response:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_session_token(token)))
        db.commit()
    clear_session_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/me", response_model=UserRead)
def me(
    response: Response,
    user: User = Depends(get_current_user),
) -> User:
    response.headers["Cache-Control"] = "no-store"
    return user
