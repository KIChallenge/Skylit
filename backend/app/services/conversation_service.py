"""Create, list, read and delete the current user's conversations."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Case, CaseStep, Conversation, Message, User
from app.schemas.conversations import ConversationSummary
from app.services.case_service import DEFAULT_CASE_TITLE, new_case

DEFAULT_CONVERSATION_TITLE = "Neuer Fall"
TITLE_FROM_MESSAGE_CHARS = 48


def display_title(
    conversation_title: str | None, case_title: str | None, first_message: str | None
) -> str:
    """Name a conversation after its event: case title, own title, first message."""
    case_title = (case_title or "").strip()
    if case_title and case_title != DEFAULT_CASE_TITLE:
        return case_title
    own = (conversation_title or "").strip()
    if own and own != DEFAULT_CONVERSATION_TITLE:
        return own
    text = " ".join((first_message or "").split())
    if not text:
        return DEFAULT_CONVERSATION_TITLE
    if len(text) <= TITLE_FROM_MESSAGE_CHARS:
        return text
    head = text[:TITLE_FROM_MESSAGE_CHARS]
    cut = head.rsplit(" ", 1)[0] or head
    return f"{cut.rstrip(' ,.;:')}…"


async def create_conversation(
    db: AsyncSession, user: User, title: str | None = None
) -> Conversation:
    """Create a conversation together with its empty case."""
    now = datetime.now(UTC)
    conversation = Conversation(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        user_id=user.id,
        title=title or DEFAULT_CONVERSATION_TITLE,
        messages=[],
    )
    conversation.case = new_case(conversation.id)
    db.add(conversation)
    await db.commit()
    return conversation


async def list_conversations(db: AsyncSession, user: User) -> list[ConversationSummary]:
    """Return the user's conversations, newest first, with their open step count."""
    # Every step that is not done still needs work from the user.
    open_steps = (
        select(func.count(CaseStep.id))
        .join(Case)
        .where(Case.conversation_id == Conversation.id, CaseStep.status != "done")
        .scalar_subquery()
    )
    case_title = (
        select(Case.title)
        .where(Case.conversation_id == Conversation.id)
        .limit(1)
        .scalar_subquery()
    )
    first_message = (
        select(Message.content)
        .where(Message.conversation_id == Conversation.id, Message.role == "user")
        .order_by(Message.created_at)
        .limit(1)
        .scalar_subquery()
    )
    rows = await db.execute(
        select(
            Conversation.id,
            Conversation.title,
            Conversation.updated_at,
            open_steps,
            case_title,
            first_message,
        )
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
    )
    return [
        ConversationSummary(
            id=id,
            title=display_title(title, case, message),
            updated_at=updated_at,
            open_steps=count,
        )
        for id, title, updated_at, count, case, message in rows
    ]


async def get_conversation(
    db: AsyncSession, user: User, conversation_id: UUID
) -> Conversation | None:
    """Return the user's conversation with messages and case, or None."""
    conversation = await db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.case).selectinload(Case.steps),
        )
        # A session that created the rows still holds their empty collections.
        .execution_options(populate_existing=True)
    )
    if conversation is not None and conversation.case is None:
        # Conversations from before this API have no case yet.
        conversation.case = new_case(conversation.id)
        await db.commit()
    return conversation


async def delete_conversation(
    db: AsyncSession, user: User, conversation_id: UUID
) -> bool:
    """Delete the user's conversation. The foreign keys cascade to its rows."""
    result = await db.execute(
        delete(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    await db.commit()
    return result.rowcount > 0
