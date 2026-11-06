"""Import every aggregate so Alembic sees the complete schema."""

from app.models.appointments import Appointment
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.calendar import CalendarEntry
from app.models.cases import Case, CaseStep
from app.models.conversations import Conversation, Message
from app.models.documents import Document
from app.models.escalations import Escalation
from app.models.forms import FormDraft
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.leistungen import Leistung
from app.models.offices import Office
from app.models.providers import Provider
from app.models.users import Profile, User

__all__ = [
    "Appointment",
    "AuditLog",
    "Base",
    "CalendarEntry",
    "Case",
    "CaseStep",
    "Conversation",
    "Document",
    "Escalation",
    "FormDraft",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "Leistung",
    "Message",
    "Office",
    "Profile",
    "Provider",
    "User",
]
