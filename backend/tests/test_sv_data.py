"""Simulated SV data query: mock service, seed, prompt guard and API (D-041)."""

import json
from datetime import date
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.llm.context import _dynamic_part
from app.main import app
from app.models import User
from app.providers.mock_sv_data import DEFAULT_REGISTER, MockSvDataService
from app.schemas.auth import ProfileUpdate
from app.schemas.sv_data import is_valid_svnr
from app.seed import SEED_DIR, seed

MARIA = "1234020674"


def register() -> dict:
    return json.loads(DEFAULT_REGISTER.read_text(encoding="utf-8"))


def test_every_register_number_is_synthetic_and_valid():
    entries = {key: value for key, value in register().items() if key.isdigit()}
    assert len(entries) == 3
    for svnr, entry in entries.items():
        assert entry["synthetic"] is True
        assert is_valid_svnr(svnr)
        # The last six digits are the birth date as DDMMYY.
        assert svnr[4:] == date.fromisoformat(entry["date_of_birth"]).strftime(
            "%d%m%y"
        )


@pytest.mark.parametrize(
    "svnr",
    ["1235020674", "123402067", "12340206745", "12340a0674", "１２３４０２０６７４"],
)
def test_invalid_numbers_fail_the_check(svnr):
    assert not is_valid_svnr(svnr)


async def test_lookup_returns_the_record():
    record = await MockSvDataService().lookup(MARIA)
    assert record is not None
    assert (record.first_name, record.last_name) == ("Maria", "Berger")
    assert record.address.postal_code == "1030"
    assert record.insurer == "OEGK"
    assert record.co_insured == []
    assert record.retrieved_at.tzinfo is not None


async def test_lookup_lists_elifs_child_as_co_insured():
    record = await MockSvDataService().lookup("7898110995")
    assert record is not None
    assert [(person.first_name, person.relation) for person in record.co_insured] == [
        ("Deniz", "Kind")
    ]


async def test_lookup_returns_none_for_an_unknown_number():
    # Valid check digit, but not in the register.
    assert is_valid_svnr("1232200188")
    assert await MockSvDataService().lookup("1232200188") is None


@pytest.mark.parametrize("svnr", ["123", "abcdefghij", "1235020674"])
async def test_lookup_rejects_a_malformed_number(svnr):
    with pytest.raises(ValueError):
        await MockSvDataService().lookup(svnr)


async def seeded_users(db_session) -> dict[str, User]:
    await seed(db_session)
    rows = await db_session.scalars(select(User).options(selectinload(User.profile)))
    return {user.persona_id: user for user in rows}


async def test_seed_fills_the_profile_from_the_register(db_session):
    users = await seeded_users(db_session)
    entries = register()
    for user in users.values():
        profile = user.profile
        entry = entries[profile.svnr]
        assert profile.bundesland == entry["address"]["bundesland"]
        assert profile.postal_code == entry["address"]["postal_code"]
        assert profile.insurer == entry["insurer"]
        assert profile.date_of_birth == date.fromisoformat(entry["date_of_birth"])
        assert profile.sv_record["svnr"] == profile.svnr
        assert profile.sv_record["address"] == entry["address"]
        assert profile.sv_retrieved_at is not None
    assert users["maria"].profile.extra["relative"]["name"] == "Anna Berger"


async def test_seed_fails_for_an_unknown_number(db_session, tmp_path):
    personas = json.loads((SEED_DIR / "personas.json").read_text(encoding="utf-8"))
    personas[0]["svnr"] = "1232200188"
    (tmp_path / "personas.json").write_text(json.dumps(personas), encoding="utf-8")
    for filename in ("providers.json", "sv_register.json"):
        (tmp_path / filename).write_text(
            (SEED_DIR / filename).read_text(encoding="utf-8"), encoding="utf-8"
        )
    with pytest.raises(ValueError, match="maria"):
        await seed(db_session, seed_dir=tmp_path)


# The replay fixtures hash the prompt: these lines must not change.
EXPECTED_PROMPT_LINES = {
    "maria": ["- Bundesland: Wien", "- PLZ: 1030", "- Versicherungsträger: OEGK"],
    "stefan": ["- Bundesland: Wien", "- PLZ: 1100", "- Versicherungsträger: SVS"],
    "elif": ["- Bundesland: Wien", "- PLZ: 1160", "- Versicherungsträger: OEGK"],
}


async def test_prompt_lines_stay_byte_identical(db_session):
    users = await seeded_users(db_session)
    case = SimpleNamespace(title="Demo", subject="self", summary=None, steps=[])
    for persona_id, expected in EXPECTED_PROMPT_LINES.items():
        profile = users[persona_id].profile
        prompt = _dynamic_part(profile, case, date(2026, 11, 6), None)
        lines = prompt.splitlines()
        start = lines.index(expected[0])
        assert lines[start : start + 3] == expected
        # Never send the SV-Nummer, the name or the street to the LLM.
        record = profile.sv_record
        for secret in (profile.svnr, record["last_name"], record["address"]["street"]):
            assert secret not in prompt


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


async def test_personas_list_has_no_sv_data(api):
    body = (await api.get("/api/personas")).text
    for leak in (MARIA, "Demogasse", "svnr", "street"):
        assert leak not in body


async def test_me_contains_the_sv_data(api):
    await api.post("/api/auth/login", json={"persona_id": "elif"})
    profile = (await api.get("/api/me")).json()["profile"]
    assert profile["svnr"] == "7898110995"
    assert profile["first_name"] == "Elif"
    assert profile["insurance_status"] == "Pflichtversichert (Angestellte)"
    assert (profile["street"], profile["city"]) == ("Mustergasse 3", "Wien")
    assert profile["co_insured"][0]["first_name"] == "Deniz"
    assert profile["sv_retrieved_at"]


@pytest.mark.parametrize(
    "field", ["svnr", "sv_record", "sv_retrieved_at", "insurance_status", "street"]
)
def test_profile_update_rejects_sv_fields(field):
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({field: "x"})


async def test_profile_patch_rejects_the_svnr(api):
    await api.post("/api/auth/login", json={"persona_id": "maria"})
    response = await api.patch("/api/me/profile", json={"svnr": "4564200188"})
    assert response.status_code == 422
    assert (await api.get("/api/me")).json()["profile"]["svnr"] == MARIA
