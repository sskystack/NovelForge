from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from novelforge.identity.models import AuthSession, User
from novelforge.identity.security import hash_session_token, password_hasher
from novelforge.settings import Settings

ORIGIN = "http://localhost:5173"
PASSWORD = "correct horse battery staple"


def register(client: TestClient, email: str = "writer@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD, "display_name": "Writer"},
    )
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, email: str = "writer@example.com") -> TestClient:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return client


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("novelforge_csrf", "")}


def test_register_normalizes_email_hashes_password_and_rejects_duplicates(
    client: TestClient,
    db_session: Session,
) -> None:
    body = register(client, "Writer@Example.com")

    assert body["email"] == "writer@example.com"
    assert "password" not in body
    user = db_session.scalar(select(User).where(User.email == body["email"]))
    assert user is not None
    assert user.password_hash != PASSWORD
    assert password_hasher.verify(PASSWORD, user.password_hash)

    duplicate = client.post(
        "/api/v1/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": "writer@example.com", "password": PASSWORD},
    )
    assert duplicate.status_code == 409
    assert duplicate.headers["content-type"].startswith("application/problem+json")
    assert duplicate.json()["code"] == "EMAIL_ALREADY_EXISTS"


def test_login_me_and_logout_use_secure_revocable_sessions(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    login(client)

    session_cookie = client.cookies.get("novelforge_session")
    csrf_cookie = client.cookies.get("novelforge_csrf")
    assert session_cookie and csrf_cookie
    session_row = db_session.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_session_token(session_cookie))
    )
    assert session_row is not None
    assert session_row.token_hash != session_cookie
    session_id = session_row.id
    assert client.get("/api/v1/auth/me").json()["email"] == "writer@example.com"

    logout = client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN, **csrf_headers(client)})
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    db_session.expire_all()
    assert db_session.get(AuthSession, session_id) is None


def test_login_sets_http_only_secure_and_same_site_cookies(client: TestClient) -> None:
    register(client)
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "writer@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(value for value in cookies if value.startswith("novelforge_session="))
    csrf_cookie = next(value for value in cookies if value.startswith("novelforge_csrf="))
    assert "httponly" in session_cookie.lower()
    assert "secure" in session_cookie.lower()
    assert "samesite=strict" in session_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()
    assert "secure" in csrf_cookie.lower()


def test_novel_crud_archive_and_restore(client: TestClient) -> None:
    register(client)
    login(client)
    headers = {"Origin": ORIGIN, **csrf_headers(client)}

    created = client.post(
        "/api/v1/novels",
        headers=headers,
        json={
            "title": "星海纪元",
            "genre": ["仙侠", "成长"],
            "premise": "外门弟子揭开星海秘密。",
            "writing_preferences": {"pov": "third_person_limited"},
        },
    )
    assert created.status_code == 201
    novel = created.json()
    novel_id = novel["id"]
    assert novel["status"] == "active"
    assert novel["created_at"].endswith("Z") or "+00:00" in novel["created_at"]

    updated = client.patch(
        f"/api/v1/novels/{novel_id}",
        headers=headers,
        json={"title": "星海纪元：新篇", "language": "zh-CN"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "星海纪元：新篇"

    archived = client.delete(f"/api/v1/novels/{novel_id}", headers=headers)
    assert archived.status_code == 204
    assert client.get("/api/v1/novels").json() == []
    assert client.get("/api/v1/novels?include_archived=true").json()[0]["status"] == "archived"

    restored = client.patch(
        f"/api/v1/novels/{novel_id}", headers=headers, json={"status": "active"}
    )
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None
    assert len(client.get("/api/v1/novels").json()) == 1


def test_users_cannot_read_update_or_archive_another_users_novel(client: TestClient) -> None:
    register(client, "owner@example.com")
    login(client, "owner@example.com")
    created = client.post(
        "/api/v1/novels",
        headers={"Origin": ORIGIN, **csrf_headers(client)},
        json={"title": "Private story"},
    )
    novel_id = created.json()["id"]

    register(client, "other@example.com")
    login(client, "other@example.com")
    headers = {"Origin": ORIGIN, **csrf_headers(client)}

    assert client.get(f"/api/v1/novels/{novel_id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/novels/{novel_id}", headers=headers, json={"title": "stolen"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/novels/{novel_id}", headers=headers).status_code == 404
    assert client.get("/api/v1/novels").json() == []


def test_invalid_credentials_csrf_and_validation_errors_are_problem_details(
    client: TestClient,
) -> None:
    register(client)
    invalid_login = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "writer@example.com", "password": "wrong password"},
    )
    assert invalid_login.status_code == 401
    assert invalid_login.json()["code"] == "INVALID_CREDENTIALS"
    login(client)

    no_csrf = client.post("/api/v1/novels", json={"title": "missing token"})
    assert no_csrf.status_code == 403
    assert no_csrf.json()["code"] == "CSRF_VALIDATION_FAILED"

    invalid_body = client.post(
        "/api/v1/novels",
        headers={"Origin": ORIGIN, **csrf_headers(client)},
        json={"title": "   "},
    )
    assert invalid_body.status_code == 422
    assert invalid_body.headers["content-type"].startswith("application/problem+json")
    assert invalid_body.json()["request_id"]


def test_auth_rejects_untrusted_origin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "https://attacker.example"},
        json={"email": "writer@example.com", "password": PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"


def test_cookie_secure_setting_defaults_to_local_development() -> None:
    assert Settings(_env_file=None).session_cookie_secure is False
    assert Settings(_env_file=None, session_cookie_secure=True).session_cookie_secure is True
