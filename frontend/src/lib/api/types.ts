/**
 * Domain aliases for UI workers. Every type points into the generated schema.
 * Never copy a backend schema here: regenerate with `npm run api:types` instead.
 */

import type { components, operations } from "./generated/schema";

type Schemas = components["schemas"];

// Auth and profile
export type Persona = Schemas["Persona"];
export type Me = Schemas["Me"];
export type Profile = Schemas["Profile"];
export type ProfileUpdate = Schemas["ProfileUpdate"];
/** Answer length the Lotse uses: "short" or "detailed". */
export type AnswerDepth = Profile["depth"];

// Conversations and messages
export type ConversationSummary = Schemas["ConversationSummary"];
export type Conversation = Schemas["Conversation"];
export type Message = Schemas["Message"];
export type MessageRole = Message["role"];
export type MessageCreate = Schemas["MessageCreate"];
export type Source = Schemas["Source"];
export type Contact = Schemas["Contact"];

// Case
export type Case = Schemas["Case"];
export type CaseStep = Schemas["CaseStep"];
export type CaseStepStatus = CaseStep["status"];
export type CaseStepCategory = CaseStep["category"];

// Documents
export type Document = Schemas["Document"];
export type DocumentStatus = Document["status"];
export type DocumentKind = Schemas["DocumentExtraction"]["kind"];
export type DocumentExtraction = Schemas["DocumentExtraction"];
export type ExtractedPatient = Schemas["ExtractedPatient"];
export type DocumentedRecommendation = Schemas["DocumentedRecommendation"];
export type FollowUpAppointment = Schemas["FollowUpAppointment"];

// Transparency
export type MessageTransparency = Schemas["MessageTransparency"];
export type Confidence = Schemas["Confidence"];
export type ConfidenceLevel = Confidence["level"];
export type AuditEntry = Schemas["AuditEntry"];
export type ToolInfo = Schemas["ToolInfo"];
export type GuardrailInfo = Schemas["GuardrailInfo"];
export type EscalationInfo = Schemas["EscalationInfo"];

// Card payloads
export type FormDraft = Schemas["FormDraft"];
export type FieldValue = Schemas["FieldValue"];
export type FieldSpec = Schemas["FieldSpec"];
export type Office = Schemas["Office"];
export type Provider = Schemas["Provider"];
export type Appointment = Schemas["Appointment"];
export type EmailDraft = Schemas["EmailDraft"];
export type Escalation = Schemas["Escalation"];
export type LeistungInfo = Schemas["LeistungInfo"];

// Kalender
export type CalendarEntry = Schemas["CalendarEntry"];
/** `kind` and `all_day` have server defaults, so the request may omit them. */
export type CalendarEntryCreate = Omit<Schemas["CalendarEntryCreate"], "kind" | "all_day">
  & Partial<Pick<Schemas["CalendarEntryCreate"], "kind" | "all_day">>;
export type CalendarKind = CalendarEntry["kind"];

/** Every card the backend can send. The generated `ToolResult.card` defines the union. */
export type Card = NonNullable<Schemas["ToolResult"]["card"]>;
export type CardType = Card["type"];
/** Narrow `Card` to one variant: `CardOf<"office">`. */
export type CardOf<T extends CardType> = Extract<Card, { type: T }>;

/**
 * The generated `DocumentSummaryCard.extraction` is `Record<string, unknown>`.
 * At runtime it follows `DocumentExtraction` (docs/contracts.md §7).
 * `toDocumentSummary` in `adapters.ts` checks the shape and returns this type.
 */
export interface DocumentSummary {
  document_id: string;
  /** `null` when the extraction does not match `DocumentExtraction`. */
  extraction: DocumentExtraction | null;
}

/** Union of all SSE events of `POST /api/conversations/{id}/messages`. */
export type StreamEvent =
  operations["event_schema_api__schema_events_get"]["responses"][200]["content"]["application/json"];
export type StreamEventType = StreamEvent["type"];
/** Narrow `StreamEvent` to one variant: `StreamEventOf<"text.delta">`. */
export type StreamEventOf<T extends StreamEventType> = Extract<StreamEvent, { type: T }>;
