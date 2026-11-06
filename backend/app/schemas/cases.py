"""Case and case step models from docs/contracts.md section 1."""

from pydantic import BaseModel, ConfigDict

from app.schemas.cards import Case, CaseStep, StepStatus

# The `case_updated` SSE event already carries `cards.Case`. The REST routes reuse
# it, so OpenAPI holds one `Case` and one `CaseStep` schema.
__all__ = ["Case", "CaseStep", "CaseStepUpdate"]


class CaseStepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StepStatus
