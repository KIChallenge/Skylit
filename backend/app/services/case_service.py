"""Read a conversation's case and let its owner change a step status."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Case, CaseStep, Conversation, User

DEFAULT_CASE_TITLE = "Mein Fall"


def new_case(conversation_id: UUID) -> Case:
    """Build an empty case. Python sets every value, so no lazy load follows."""
    now = datetime.now(UTC)
    return Case(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        conversation_id=conversation_id,
        title=DEFAULT_CASE_TITLE,
        subject="self",
        summary="",
        steps=[],
    )


async def get_case(
    db: AsyncSession, user: User, conversation_id: UUID
) -> Case | None:
    """Return the case of the user's conversation, or None for a foreign id."""
    statement = (
        select(Case)
        .join(Conversation)
        .where(Case.conversation_id == conversation_id, Conversation.user_id == user.id)
        .options(selectinload(Case.steps))
        # A session that created the case still holds its empty step list.
        .execution_options(populate_existing=True)
    )
    case = await db.scalar(statement)
    if case is not None:
        return case
    owned = await db.scalar(
        select(Conversation.id).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    if owned is None:
        return None
    # Conversations from before this API have no case yet.
    case = new_case(conversation_id)
    db.add(case)
    await db.commit()
    return case


async def update_step_status(
    db: AsyncSession, user: User, step_id: UUID, status: str
) -> CaseStep | None:
    """Set the status of the user's step. Return None for a foreign or unknown id."""
    step = await db.scalar(
        select(CaseStep)
        .join(Case)
        .join(Conversation)
        .where(CaseStep.id == step_id, Conversation.user_id == user.id)
        .options(selectinload(CaseStep.case))
    )
    if step is None:
        return None
    step.status = status
    step.case.updated_at = datetime.now(UTC)
    await db.commit()
    return step
