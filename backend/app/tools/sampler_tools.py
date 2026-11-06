"""SAMPLER intake: one health question per turn, as a multiple-choice card."""

from typing import get_args

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import cards
from app.tools.registry import ToolContext, ToolError, ToolOutput, registry

STEPS: tuple[str, ...] = get_args(cards.SamplerStep)
STEP_LABELS: dict[str, str] = {
    "S_O": "Beschwerde · Beginn",
    "S_P": "Beschwerde · Auslöser und Linderung",
    "S_Q": "Beschwerde · Art",
    "S_R": "Beschwerde · Ort und Ausstrahlung",
    "S_S": "Beschwerde · Stärke",
    "S_T": "Beschwerde · Zeitverlauf",
    "A": "Allergien",
    "M": "Medikamente",
    "P": "Vorgeschichte",
    "L": "Zuletzt",
    "E": "Ereignisse davor",
    "R": "Risikofaktoren",
}
DEFAULT_FREE_TEXT_LABEL = "In eigenen Worten beschreiben (optional)"


class AskSamplerInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    step: cards.SamplerStep
    question: str = Field(min_length=1, max_length=200)
    options: list[str] = Field(min_length=2, max_length=6)
    multiple: bool = False
    free_text_label: str | None = Field(default=None, max_length=80)


@registry.tool(
    "ask_sampler",
    label="Rückfrage wird vorbereitet",
    description=(
        "Stellt der Person genau eine SAMPLER-Frage als Karte mit 2 bis 6 kurzen "
        "Antwortoptionen und einem Beschreibungsfeld. Nutze das Tool nur bei einer "
        "geschilderten gesundheitlichen Beschwerde ohne Notfall. Reihenfolge: S_O, "
        "S_P, S_Q, S_R, S_S, S_T (OPQRST), dann A, M, P, L, E, R. Überspringe "
        "Schritte, die schon beantwortet sind. Nach dem Aufruf endet deine Antwort; "
        "die Person antwortet über die Karte."
    ),
    input_model=AskSamplerInput,
)
async def ask_sampler(input: AskSamplerInput, ctx: ToolContext) -> ToolOutput:
    # Life threat first: an emergency turn never asks SAMPLER questions.
    if ctx.emergency:
        raise ToolError(
            "Notfall erkannt: Stelle keine SAMPLER-Frage. Nenne die Notrufnummern "
            "und antworte kurz und ruhig."
        )
    cleaned = (option.strip() for option in input.options)
    options = list(dict.fromkeys(option for option in cleaned if option))
    question = cards.SamplerQuestion(
        step=input.step,
        step_label=STEP_LABELS[input.step],
        position=STEPS.index(input.step) + 1,
        total=len(STEPS),
        question=input.question,
        options=options,
        multiple=input.multiple,
        free_text_label=input.free_text_label or DEFAULT_FREE_TEXT_LABEL,
    )
    return ToolOutput(
        result={
            "ok": True,
            "shown": True,
            "step": input.step,
            "note": "Die Karte ist sichtbar. Warte auf die Antwort der Person.",
        },
        card=cards.SamplerQuestionCard(question=question),
    )
