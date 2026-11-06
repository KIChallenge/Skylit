import { toCards, type CardOf, type Message } from "@/lib/api";

type SamplerQuestion = CardOf<"sampler_question">["question"];

export type SamplerStep = {
  question: SamplerQuestion;
  /** The answer text without the "<step label>: " prefix. Missing while the question is open. */
  answer?: string;
};

export type SamplerSessionState =
  /** The latest question waits for an answer. */
  | "asking"
  /** An answer went out; the Lotse prepares the next question or the summary. */
  | "loading"
  /** The Lotse answered without a new question: the intake is over. */
  | "done";

export type SamplerSession = {
  steps: SamplerStep[];
  state: SamplerSessionState;
  /** True when the open question belongs to the latest message and nothing streams. */
  answerable: boolean;
};

export type SamplerGrouping = {
  /** Messages the chat must not render: later SAMPLER turns and the answers to them. */
  hidden: Set<string>;
  /** Keyed by the id of the first SAMPLER message; that message shows the session card. */
  sessions: Map<string, SamplerSession>;
  /** Hide the live text while it belongs to a SAMPLER step, so no extra bubble flashes up. */
  hideLiveText: boolean;
};

export type LiveAnswer = {
  streaming: boolean;
  text: string;
  cards: unknown;
};

/** Longer live text is a real answer (the summary), not the one short sentence before a question. */
const STEP_TEXT_LIMIT = 160;

const samplerCards = (cards: unknown) => toCards(cards).filter((card) => card.type === "sampler_question");

/** A message whose only cards are SAMPLER questions. Other cards end the grouping. */
function samplerQuestionOf(cards: unknown): SamplerQuestion | null {
  const all = toCards(cards);
  const questions = samplerCards(cards);
  if (!questions.length || questions.length !== all.length) return null;
  return questions[questions.length - 1].question;
}

/** "Beschwerde · Beginn: Seit gestern" → "Seit gestern". Free text from the composer stays as is. */
export function stripStepLabel(content: string, stepLabel: string): string {
  const prefix = `${stepLabel}:`;
  return content.startsWith(prefix) ? content.slice(prefix.length).trim() : content.trim();
}

/**
 * Group consecutive SAMPLER turns into one session, so the chat shows one card that
 * switches questions instead of a new bubble per question.
 *
 * A user message after a SAMPLER question counts as its answer when the next assistant
 * message asks again, when it was sent through the card (it starts with the step label),
 * or when it is the latest message. Otherwise it stays a normal bubble and ends the session.
 */
export function groupSamplerTurns(
  messages: Message[],
  cardsOf: (message: Message) => unknown,
  live: LiveAnswer,
): SamplerGrouping {
  const hidden = new Set<string>();
  const sessions = new Map<string, SamplerSession>();
  let open: { id: string; session: SamplerSession } | null = null;

  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index];
    if (message.role !== "assistant") continue;
    const question = samplerQuestionOf(cardsOf(message));
    if (!question) {
      if (open) open.session.state = "done";
      open = null;
      continue;
    }
    if (open) hidden.add(message.id);
    else {
      open = { id: message.id, session: { steps: [], state: "asking", answerable: false } };
      sessions.set(message.id, open.session);
    }
    const step: SamplerStep = { question };
    open.session.steps.push(step);

    const reply = messages[index + 1];
    if (!reply || reply.role !== "user") continue;
    const next = messages[index + 2];
    const asksAgain = next?.role === "assistant" && samplerQuestionOf(cardsOf(next)) !== null;
    const viaCard = reply.content.startsWith(`${question.step_label}:`);
    if (asksAgain || viaCard || !next) {
      step.answer = stripStepLabel(reply.content, question.step_label);
      hidden.add(reply.id);
      index += 1;
    } else {
      open.session.state = "done";
      open = null;
    }
  }

  let hideLiveText = false;
  if (open) {
    const last = open.session.steps[open.session.steps.length - 1];
    const latestId = messages[messages.length - 1]?.id;
    if (last.answer === undefined) {
      open.session.answerable = !live.streaming && latestId === hiddenOrFirst(open.id, messages, hidden);
    } else if (live.streaming) {
      open.session.state = "loading";
      const liveQuestion = samplerCards(live.cards);
      hideLiveText = liveQuestion.length > 0 || live.text.length < STEP_TEXT_LIMIT;
    } else {
      // The answer went out, but no reply arrived (for example after an error).
      open.session.state = "loading";
    }
  }
  return { hidden, sessions, hideLiveText };
}

/** The id of the latest SAMPLER message in the open session (it may be hidden). */
function hiddenOrFirst(firstId: string, messages: Message[], hidden: Set<string>): string {
  let latest = firstId;
  let started = false;
  for (const message of messages) {
    if (message.id === firstId) started = true;
    if (started && message.role === "assistant" && (message.id === firstId || hidden.has(message.id))) latest = message.id;
  }
  return latest;
}
