"""Source-backed knowledge retrieval for administrative questions."""

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.models import Profile
from app.rag import retriever
from app.tools.registry import ToolContext, ToolOutput, registry


class SearchKnowledgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1)
    category: str | None = Field(default=None, min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@registry.tool(
    "search_knowledge",
    label="Offizielle Quellen werden gesucht",
    description=(
        "Sucht offizielle Quellen zu Leistungen und administrativen Schritten. "
        "Nutze die Quellen für belegte Aussagen. Nutze das Tool nicht für Diagnosen, "
        "Befundinterpretation, Dosierung oder Therapieentscheidungen. "
        "Erfinde bei leeren Treffern keine Antwort; eskaliere fehlende Quellen."
    ),
    input_model=SearchKnowledgeInput,
)
async def search_knowledge(
    input: SearchKnowledgeInput, ctx: ToolContext
) -> ToolOutput:
    bundesland = await ctx.db.scalar(
        select(Profile.bundesland).where(Profile.user_id == ctx.user.id)
    )
    chunks = await retriever.search(
        ctx.db,
        input.query,
        category=input.category,
        bundesland=bundesland,
        top_k=input.top_k,
    )
    return ToolOutput(
        result={
            "chunks": [
                chunk.model_dump(mode="json", include={"heading", "content", "source"})
                for chunk in chunks
            ]
        }
    )
