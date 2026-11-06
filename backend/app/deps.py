"""Shared FastAPI dependencies: database session, session cookie, current user."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyCookie
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import get_db
from app.models import User

__all__ = [
    "SESSION_COOKIE",
    "SESSION_MAX_AGE",
    "api_error",
    "current_user",
    "get_db",
    "sign_session",
]

SESSION_COOKIE = "lotse_session"
# Mock persona login: one week keeps a demo laptop logged in across restarts.
SESSION_MAX_AGE = 7 * 24 * 60 * 60
_SESSION_SALT = "lotse-session"

# Documents the cookie in OpenAPI; current_user owns the 401.
session_cookie = APIKeyCookie(name=SESSION_COOKIE, auto_error=False)


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    """Build an HTTPException that the app renders as the contract error body."""
    return HTTPException(
        status_code=status_code, detail={"code": code, "message": message}
    )


def _serializer() -> URLSafeTimedSerializer:
    # Read the key per call so a changed setting takes effect at once.
    return URLSafeTimedSerializer(settings.secret_key, salt=_SESSION_SALT)


def sign_session(user_id: UUID) -> str:
    return _serializer().dumps(str(user_id))


def _read_session(token: str) -> UUID | None:
    try:
        return UUID(_serializer().loads(token, max_age=SESSION_MAX_AGE))
    except (BadData, TypeError, ValueError):
        return None


async def current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(session_cookie)],
) -> User:
    user_id = _read_session(token) if token else None
    user = (
        await db.get(User, user_id, options=[selectinload(User.profile)])
        if user_id
        else None
    )
    if user is None:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "unauthorized",
            "Bitte melden Sie sich an.",
        )
    return user
