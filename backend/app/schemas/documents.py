"""Document models from docs/contracts.md sections 1 and 5."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DocumentKind = Literal[
    "discharge_letter", "finding", "vaccination_record", "notice", "other"
]
DocumentStatus = Literal["processing", "ready", "failed"]
RecommendationTopic = Literal[
    "rehabilitation",
    "care_allowance",
    "mobile_care",
    "follow_up",
    "aids",
    "transport",
    "prescription_fee_exemption",
    "nutrition",
    "social_services",
    "other",
]


class _ExtractionModel(BaseModel):
    # Strict json_schema mode needs this flag. Validation still ignores extra keys.
    model_config = ConfigDict(json_schema_extra={"additionalProperties": False})


class ExtractedPatient(_ExtractionModel):
    name: str | None
    date_of_birth: str | None
    address: str | None
    postal_code: str | None
    insurer: str | None
    svnr: str | None


class DocumentedRecommendation(_ExtractionModel):
    topic: RecommendationTopic
    quote: str
    section: str | None


class FollowUpAppointment(_ExtractionModel):
    what: str
    when: str | None
    quote: str


class DocumentExtraction(_ExtractionModel):
    kind: DocumentKind
    issuer: str | None
    document_date: str | None
    patient: ExtractedPatient
    living_situation: str | None
    documented_recommendations: list[DocumentedRecommendation]
    follow_up_appointments: list[FollowUpAppointment]
    warnings_in_document: list[str]
    confidence_note: str | None


class Document(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    mime_type: str
    status: DocumentStatus
    kind: DocumentKind | None
    extracted: DocumentExtraction | None
    created_at: datetime
