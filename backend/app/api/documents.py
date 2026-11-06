"""Upload documents, poll their extraction and download the original file."""

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.deps import api_error, current_user, get_db
from app.documents.extract import DocumentError
from app.documents.pipeline import process_document, store_upload
from app.models import Conversation, Document, User
from app.schemas.documents import Document as DocumentResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

_FALLBACK_FILENAME = "Dokument"
_UPLOAD_ERROR_STATUS = {
    "unsupported_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    "file_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
    "empty_file": status.HTTP_400_BAD_REQUEST,
}


def background_sessions() -> SessionFactory:
    """The extraction outlives the request, so it opens its own session."""
    return SessionLocal


async def _process_in_background(sessions: SessionFactory, document_id: UUID) -> None:
    try:
        async with sessions() as session:
            await process_document(session, document_id)
    except Exception:
        # process_document handles extraction errors. Only database errors end here.
        logger.exception("Document processing crashed: document_id=%s", document_id)


async def _owned_document(id: UUID, db: AsyncSession, user: User) -> Document:
    document = await db.scalar(
        select(Document).where(Document.id == id, Document.user_id == user.id)
    )
    if document is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            "Dieses Dokument wurde nicht gefunden.",
        )
    return document


def _mime_type(file: UploadFile) -> str:
    # A client may send parameters, for example "application/pdf; name=brief.pdf".
    return (file.content_type or "").split(";")[0].strip().lower()


def _filename(file: UploadFile) -> str:
    # PostgreSQL text columns reject NUL characters.
    return (file.filename or "").replace("\x00", "") or _FALLBACK_FILENAME


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: DbSession,
    user: CurrentUser,
    sessions: Annotated[SessionFactory, Depends(background_sessions)],
    conversation_id: Annotated[UUID | None, Form()] = None,
) -> DocumentResponse:
    if conversation_id is not None:
        found = await db.scalar(
            select(Conversation.id).where(
                Conversation.id == conversation_id, Conversation.user_id == user.id
            )
        )
        if found is None:
            raise api_error(
                status.HTTP_404_NOT_FOUND, "not_found", "Diesen Fall gibt es nicht."
            )

    # One byte over the limit is enough for store_upload to reject the file.
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    try:
        document = await store_upload(
            db, user, _filename(file), _mime_type(file), data
        )
    except DocumentError as exc:
        raise api_error(
            _UPLOAD_ERROR_STATUS.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR),
            exc.code,
            exc.message,
        ) from None

    document.conversation_id = conversation_id
    response = DocumentResponse.model_validate(document)
    # The commit frees the connection: the extraction can take a minute or more.
    await db.commit()
    background_tasks.add_task(_process_in_background, sessions, document.id)
    return response


@router.get("/documents/{id}", response_model=DocumentResponse)
async def read_document(id: UUID, db: DbSession, user: CurrentUser) -> Document:
    return await _owned_document(id, db, user)


@router.get("/documents/{id}/file", response_class=FileResponse)
async def download_document(
    id: UUID, db: DbSession, user: CurrentUser
) -> FileResponse:
    document = await _owned_document(id, db, user)
    if not Path(document.storage_path).is_file():
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            "Die Datei ist nicht mehr vorhanden. Bitte laden Sie sie erneut hoch.",
        )
    return FileResponse(
        document.storage_path,
        media_type=document.mime_type,
        filename=document.filename,
        content_disposition_type="inline",
        # The browser must keep to the checked mime type of this user-supplied file.
        headers={"X-Content-Type-Options": "nosniff"},
    )
