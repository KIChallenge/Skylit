"""The tool that reads an uploaded document: `get_document`."""

from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models import Document
from app.schemas import cards
from app.tools.registry import ToolContext, ToolError, ToolOutput, registry


class GetDocumentInput(BaseModel):
    document_id: UUID = Field(description="Id des hochgeladenen Dokuments.")


@registry.tool(
    "get_document",
    label="Dokument wird gelesen",
    description=(
        "Liefert die Angaben aus einem hochgeladenen Dokument, mit wörtlichen Zitaten, "
        "und zeigt der Person eine Zusammenfassung. Nutze das Tool, sobald eine "
        "document_id vorliegt und du aus dem Dokument zitieren willst. "
        "Nutze es nicht ohne document_id und nicht für Dokumente aus der Wissensbasis. "
        "Nutze es nicht, um Diagnosen oder Befunde zu deuten."
    ),
    input_model=GetDocumentInput,
)
async def get_document(input: GetDocumentInput, ctx: ToolContext) -> ToolOutput:
    # The session may hold this row from the start of the turn, with an old status.
    document = await ctx.db.scalar(
        select(Document)
        .where(Document.id == input.document_id, Document.user_id == ctx.user.id)
        .execution_options(populate_existing=True)
    )
    if document is None:
        raise ToolError("Es gibt kein Dokument mit dieser document_id.")
    if document.status == "processing":
        raise ToolError(
            "Das Dokument wird noch verarbeitet. Warte, bis es fertig ist. "
            "Bitte die Person, es kurz danach noch einmal zu versuchen."
        )
    if document.extracted is None:
        raise ToolError(
            document.error or "Das Dokument konnte nicht verarbeitet werden."
        )
    return ToolOutput(
        result=document.extracted,
        card=cards.DocumentSummaryCard(
            document_id=document.id, extraction=document.extracted
        ),
    )
