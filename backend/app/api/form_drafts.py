"""Owner-only form metadata and editable PDF downloads."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import api_error, current_user, get_db
from app.models import FormDraft, User
from app.schemas import cards
from app.tools.form_tools import to_form_draft

router = APIRouter(tags=["form-drafts"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


async def _owned_draft(id: UUID, db: AsyncSession, user: User) -> FormDraft:
    row = await db.scalar(
        select(FormDraft).where(FormDraft.id == id, FormDraft.user_id == user.id)
    )
    if row is None:
        raise api_error(
            404, "not_found", "Dieser Formularentwurf wurde nicht gefunden."
        )
    return row


@router.get("/form-drafts/{id}", response_model=cards.FormDraft)
async def read_form_draft(
    id: UUID, db: DbSession, user: CurrentUser
) -> cards.FormDraft:
    return to_form_draft(await _owned_draft(id, db, user))


@router.get("/form-drafts/{id}/pdf", response_class=FileResponse)
async def download_form_draft(
    id: UUID, db: DbSession, user: CurrentUser
) -> FileResponse:
    row = await _owned_draft(id, db, user)
    if not row.pdf_path or not Path(row.pdf_path).is_file():
        raise api_error(404, "not_found", "Die PDF-Datei wurde nicht gefunden.")
    return FileResponse(
        row.pdf_path,
        media_type="application/pdf",
        filename=f"{row.form_id}-{row.id}.pdf",
    )
