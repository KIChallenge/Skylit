/**
 * Runtime guards for the places where the generated schema is too broad
 * (docs/contracts.md §7). The guards never fill in values: a value that does not
 * match its shape becomes `null`, or the list drops it.
 */

import type {
  Card,
  CardOf,
  CardType,
  DocumentExtraction,
  DocumentSummary,
  StreamEvent,
  StreamEventType,
} from "./types";

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

/** Optional backend fields may be missing, `null` or a string. */
function isOptionalString(value: unknown): boolean {
  return value === undefined || isNullableString(value);
}

function hasStrings(record: unknown, keys: readonly string[]): record is UnknownRecord {
  return isRecord(record) && keys.every((key) => isString(record[key]));
}

function isArrayOf(value: unknown, check: (item: unknown) => boolean): value is unknown[] {
  return Array.isArray(value) && value.every(check);
}

const isSource = (value: unknown) => hasStrings(value, ["title", "url", "publisher"]);
const isFieldSpec = (value: unknown) =>
  hasStrings(value, ["key", "label"]) && isOptionalString(value.hint);
const isFieldValue = (value: unknown) => hasStrings(value, ["key", "label", "value", "source"]);
const isProvider = (value: unknown) => hasStrings(value, ["id", "name", "kind"]);
const isContact = (value: unknown) => hasStrings(value, ["name"]);

/** One check per card type. The `Record` type makes the compiler demand every variant. */
const CARD_CHECKS: Record<CardType, (card: UnknownRecord) => boolean> = {
  form_draft: ({ form_draft: draft }) =>
    hasStrings(draft, ["id", "form_id", "title", "pdf_url"]) &&
    isArrayOf(draft.filled, isFieldValue) &&
    isArrayOf(draft.missing, isFieldSpec) &&
    isArrayOf(draft.to_be_filled_by_others, isFieldSpec),
  office: ({ office }) => hasStrings(office, ["id", "name", "organisation", "address"]),
  provider_list: ({ providers }) => isArrayOf(providers, isProvider),
  appointment: ({ appointment }) =>
    hasStrings(appointment, ["id", "start", "end", "ics_url"]) && isProvider(appointment.provider),
  email_draft: ({ email }) => hasStrings(email, ["to_label", "subject", "body"]),
  escalation: ({ escalation }) =>
    hasStrings(escalation, ["id", "reason_code", "handover_summary"]) &&
    isContact(escalation.target),
  document_summary: (card) => isString(card.document_id) && isRecord(card.extraction),
  sampler_question: ({ question }) =>
    hasStrings(question, ["step", "step_label", "question", "free_text_label"]) &&
    isArrayOf(question.options, isString) &&
    typeof question.multiple === "boolean" &&
    Number.isInteger(question.position) &&
    Number.isInteger(question.total),
  leistung: ({ leistung }) =>
    hasStrings(leistung, ["id", "title", "short", "office_hint"]) &&
    isArrayOf(leistung.conditions, isString) &&
    isArrayOf(leistung.documents_needed, isString) &&
    isSource(leistung.source),
};

/** Return the card when its type is known and its shape fits, else `null`. */
export function toCard(value: unknown): Card | null {
  if (!isRecord(value) || !isString(value.type)) return null;
  if (!Object.hasOwn(CARD_CHECKS, value.type)) return null;
  const check = CARD_CHECKS[value.type as CardType];
  return check(value) ? (value as unknown as Card) : null;
}

/** Keep the valid cards of `Message.cards`. Unknown or broken cards drop out. */
export function toCards(values: unknown): Card[] {
  if (!Array.isArray(values)) return [];
  return values.map(toCard).filter((card): card is Card => card !== null);
}

const isRecommendation = (value: unknown) =>
  hasStrings(value, ["topic", "quote"]) && isNullableString(value.section);
const isFollowUp = (value: unknown) =>
  hasStrings(value, ["what", "quote"]) && isNullableString(value.when);
const PATIENT_KEYS = ["name", "date_of_birth", "address", "postal_code", "insurer", "svnr"];

/** Return the extraction when it matches `DocumentExtraction`, else `null`. */
export function toDocumentExtraction(value: unknown): DocumentExtraction | null {
  if (!isRecord(value) || !isString(value.kind)) return null;
  const { patient } = value;
  const valid =
    isNullableString(value.issuer) &&
    isNullableString(value.document_date) &&
    isNullableString(value.living_situation) &&
    isNullableString(value.confidence_note) &&
    isRecord(patient) &&
    PATIENT_KEYS.every((key) => isNullableString(patient[key])) &&
    isArrayOf(value.documented_recommendations, isRecommendation) &&
    isArrayOf(value.follow_up_appointments, isFollowUp) &&
    isArrayOf(value.warnings_in_document, isString);
  return valid ? (value as unknown as DocumentExtraction) : null;
}

/** Read a `document_summary` card with a typed extraction. */
export function toDocumentSummary(card: CardOf<"document_summary">): DocumentSummary {
  return { document_id: card.document_id, extraction: toDocumentExtraction(card.extraction) };
}

/** Every event type of the generated union. The `Record` type keeps this list complete. */
const STREAM_EVENT_TYPES: Record<StreamEventType, true> = {
  "message.created": true,
  emergency: true,
  status: true,
  "text.delta": true,
  "tool.called": true,
  "tool.result": true,
  "case.updated": true,
  escalation: true,
  sources: true,
  "message.completed": true,
  error: true,
};

/** True for event types the generated union knows. The facade drops all others. */
export function isKnownStreamEvent(event: { type: string }): event is StreamEvent {
  return Object.hasOwn(STREAM_EVENT_TYPES, event.type);
}

/**
 * Prefix a backend-relative URL (`/api/...`) with the backend origin.
 * Absolute URLs, such as external source links, stay unchanged.
 */
export function resolveApiUrl(url: string, apiOrigin: string): string {
  if (url.startsWith("/") && !url.startsWith("//")) {
    return `${apiOrigin.replace(/\/+$/, "")}${url}`;
  }
  return url;
}
