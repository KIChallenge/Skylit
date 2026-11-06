import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import get_db
from app.deps import SESSION_COOKIE
from app.main import app
from app.seed import seed


@pytest_asyncio.fixture
async def api(db_session):
    await seed(db_session)

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


async def login(api, persona_id="maria"):
    response = await api.post("/api/auth/login", json={"persona_id": persona_id})
    assert response.status_code == 200
    return response


async def test_personas_lists_the_three_seeded_personas(api):
    response = await api.get("/api/personas")
    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == ["maria", "stefan", "elif"]


async def test_login_sets_http_only_cookie_and_returns_me(api):
    response = await login(api)
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    body = response.json()
    assert body["persona_id"] == "maria"
    assert body["profile"]["postal_code"] == "1030"


async def test_me_requires_a_valid_session(api):
    response = await api.get("/api/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"

    await login(api)
    response = await api.get("/api/me")
    assert response.status_code == 200
    assert response.json()["display_name"] == "Maria Berger"


async def test_tampered_cookie_is_rejected(api):
    await login(api)
    token = api.cookies[SESSION_COOKIE]
    api.cookies.set(SESSION_COOKIE, token[:-2] + "xx")
    response = await api.get("/api/me")
    assert response.status_code == 401


async def test_unknown_persona_returns_contract_error(api):
    response = await api.post("/api/auth/login", json={"persona_id": "nobody"})
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Diese Persona gibt es nicht."}
    }


async def test_profile_patch_persists(api):
    await login(api)
    response = await api.patch(
        "/api/me/profile", json={"language": "en", "depth": "detailed"}
    )
    assert response.status_code == 200
    assert response.json()["profile"]["language"] == "en"
    response = await api.get("/api/me")
    assert response.json()["profile"]["depth"] == "detailed"


async def test_logout_clears_the_cookie(api):
    await login(api)
    response = await api.post("/api/auth/logout")
    assert response.status_code == 204
    assert f'{SESSION_COOKIE}=""' in response.headers["set-cookie"]
    api.cookies.clear()
    assert (await api.get("/api/me")).status_code == 401
