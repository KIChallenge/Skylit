"""Cards and the shared DTOs they carry (contracts.md §1 and §2)."""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CaseSubject = Literal["self", "parent", "child", "partner", "other"]
StepStatus = Literal["open", "in_progress", "done", "blocked"]
StepCategory = Literal[
    "info", "form", "document", "appointment", "contact", "escalation"
]
ProviderKind = Literal[
    "gp", "specialist", "care_counselling", "mobile_care", "therapy", "course"
]
EscalationReason = Literal[
    "emergency",
    "medical_question",
    "legal_uncertainty",
    "no_source",
    "user_stuck",
    "social_crisis",
]
# SAMPLER order. S expands into OPQRST: Onset, Provocation/Palliation, Quality,
# Region/Radiation, Severity, Time.
SamplerStep = Literal[
    "S_O", "S_P", "S_Q", "S_R", "S_S", "S_T", "A", "M", "P", "L", "E", "R"
]


class Schema(BaseModel):
    """Base for DTOs. `from_attributes` lets them read ORM rows directly."""

    model_config = ConfigDict(from_attributes=True)


class Source(Schema):
    title: str
    url: str
    publisher: str
    # The day the team read a knowledge-base source. None for uploads and Leistungen.
    retrieved: date | None = None


class Contact(Schema):
    name: str
    phone: str | None = None
    url: str | None = None
    hours: str | None = None
    note: str | None = None


class FieldValue(Schema):
    key: str
    label: str
    value: str
    source: Literal["conversation", "document", "profile"]


class FieldSpec(Schema):
    key: str
    label: str
    hint: str | None = None


class FormDraft(Schema):
    id: UUID
    form_id: str
    title: str
    filled: list[FieldValue]
    missing: list[FieldSpec]
    to_be_filled_by_others: list[FieldSpec]
    pdf_url: str
    created_at: datetime


class Office(Schema):
    id: str
    name: str
    organisation: str
    address: str
    postal_code: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    url: str | None = None
    hours: str | None = None
    maps_url: str | None = None


class Provider(Schema):
    id: str
    name: str
    kind: ProviderKind
    specialty: str | None = None
    address: str | None = None
    postal_code: str | None = None
    distance_km: float | None = None
    phone: str | None = None
    website: str | None = None
    # False for Stadt Wien open data (data.wien.gv.at, CC BY 4.0).
    demo: bool = True


class Appointment(Schema):
    id: UUID
    provider: Provider
    start: datetime
    end: datetime
    ics_url: str
    demo: Literal[True] = True


class EmailDraft(Schema):
    to_label: str
    to_email: str | None = None
    subject: str
    body: str


class Escalation(Schema):
    id: UUID
    reason_code: EscalationReason
    target: Contact
    handover_summary: str
    created_at: datetime


class LeistungInfo(Schema):
    id: str
    title: str
    short: str
    conditions: list[str]
    office_hint: str
    form_ids: list[str]
    documents_needed: list[str]
    source: Source


class SamplerQuestion(Schema):
    step: SamplerStep
    step_label: str
    position: int
    total: int
    question: str
    options: list[str]
    multiple: bool
    free_text_label: str


class FormDraftCard(Schema):
    type: Literal["form_draft"] = "form_draft"
    form_draft: FormDraft


class OfficeCard(Schema):
    type: Literal["office"] = "office"
    office: Office


class ProviderListCard(Schema):
    type: Literal["provider_list"] = "provider_list"
    providers: list[Provider]
    # True when at least one provider is invented demo data.
    demo: bool = True
    # Where `distance_km` starts: the postal code centre or the shared location.
    origin: Literal["postal_code", "location"] = "postal_code"


class AppointmentCard(Schema):
    type: Literal["appointment"] = "appointment"
    appointment: Appointment
    demo: Literal[True] = True


class EmailDraftCard(Schema):
    type: Literal["email_draft"] = "email_draft"
    email: EmailDraft


class EscalationCard(Schema):
    type: Literal["escalation"] = "escalation"
    escalation: Escalation


class DocumentSummaryCard(Schema):
    type: Literal["document_summary"] = "document_summary"
    document_id: UUID
    # DocumentExtraction (contracts.md §5) arrives with the document pipeline task.
    extraction: dict[str, Any]


class LeistungCard(Schema):
    type: Literal["leistung"] = "leistung"
    leistung: LeistungInfo


class SamplerQuestionCard(Schema):
    type: Literal["sampler_question"] = "sampler_question"
    question: SamplerQuestion


Card = Annotated[
    FormDraftCard
    | OfficeCard
    | ProviderListCard
    | AppointmentCard
    | EmailDraftCard
    | EscalationCard
    | DocumentSummaryCard
    | LeistungCard
    | SamplerQuestionCard,
    Field(discriminator="type"),
]


class CaseStep(Schema):
    id: UUID
    title: str
    description: str
    status: StepStatus
    category: StepCategory
    leistung_id: str | None = None
    due_hint: str | None = None
    related_card: Card | None = None
    position: int


class Case(Schema):
    id: UUID
    title: str
    subject: CaseSubject
    summary: str
    steps: list[CaseStep]
    updated_at: datetime
