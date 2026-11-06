"""Mock persona login, logout and the current user's profile."""

from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    api_error,
    current_user,
    get_db,
    sign_session,
)
from app.models import User
from app.schemas.auth import LoginRequest, Me, Persona, Profile, ProfileUpdate
from app.seed import SEED_DIR, load_records

router = APIRouter(tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


@cache
def _persona_order() -> dict[str, int]:
    # The users table has no position column; the seed file defines card order.
    records = load_records(SEED_DIR / "personas.json")
    return {record["persona_id"]: index for index, record in enumerate(records)}


def _cookie_options() -> dict[str, object]:
    return {
        "path": "/",
        "httponly": True,
        "samesite": "lax",
        "secure": settings.app_env == "production",
    }


def to_me(user: User) -> Me:
    profile = Profile.model_validate(user.profile)
    record = user.profile.sv_record
    if record:
        # Only the logged-in user sees the SV data; /personas never does.
        address = record["address"]
        profile = Profile.model_validate(
            {
                **profile.model_dump(),
                "first_name": record["first_name"],
                "last_name": record["last_name"],
                "insurance_status": record["insurance_status"],
                "street": address["street"],
                "city": address["city"],
                "co_insured": record.get("co_insured", []),
            }
        )
    return Me(
        user_id=user.id,
        persona_id=user.persona_id,
        display_name=user.display_name,
        profile=profile,
    )


@router.get("/personas", response_model=list[Persona])
async def list_personas(db: DbSession) -> list[Persona]:
    users = (await db.scalars(select(User))).all()
    order = _persona_order()
    users = sorted(
        users,
        key=lambda user: (order.get(user.persona_id, len(order)), user.persona_id),
    )
    return [
        Persona(
            id=user.persona_id,
            display_name=user.display_name,
            tagline=user.tagline,
            avatar_emoji=user.avatar_emoji,
        )
        for user in users
    ]


@router.post("/auth/login", response_model=Me)
async def login(body: LoginRequest, response: Response, db: DbSession) -> Me:
    user = await db.scalar(
        select(User)
        .options(selectinload(User.profile))
        .where(User.persona_id == body.persona_id)
    )
    if user is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND, "not_found", "Diese Persona gibt es nicht."
        )
    response.set_cookie(
        SESSION_COOKIE,
        sign_session(user.id),
        max_age=SESSION_MAX_AGE,
        **_cookie_options(),
    )
    return to_me(user)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(current_user)],
)
async def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, **_cookie_options())
    return response


@router.get("/me", response_model=Me)
async def read_me(user: CurrentUser) -> Me:
    return to_me(user)


@router.patch("/me/profile", response_model=Me)
async def update_profile(body: ProfileUpdate, user: CurrentUser, db: DbSession) -> Me:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user.profile, field, value)
    await db.flush()
    me = to_me(user)
    await db.commit()
    return me
