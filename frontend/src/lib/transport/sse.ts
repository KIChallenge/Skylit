/** Incremental parser for `text/event-stream`, after the WHATWG parsing rules. */

import { failure, isRecord } from "./errors.ts";

/** One dispatched SSE block before JSON decoding. */
export interface SseMessage {
  /** Value of the `event:` line. `null` when the block has none. */
  event: string | null;
  /** All `data:` lines, joined with a line feed. */
  data: string;
}

/** Smallest shape of a stream event. Generated event types fit this constraint. */
export interface SseEventBase {
  type: string;
}

/** Event type for consumers without generated types. */
export interface UnknownSseEvent extends SseEventBase {
  [key: string]: unknown;
}

export interface SseParser {
  /** Consume one chunk and return every block that this chunk completes. */
  push(chunk: Uint8Array): SseMessage[];
}

/**
 * A block without its closing blank line never dispatches.
 * The parser therefore needs no end-of-stream step.
 */
export function createSseParser(): SseParser {
  const decoder = new TextDecoder("utf-8");
  let partialLine = "";
  let skipLineFeed = false;
  let eventName: string | null = null;
  let dataLines: string[] = [];

  function consumeLine(line: string, messages: SseMessage[]): void {
    if (line === "") {
      if (dataLines.length > 0) {
        messages.push({ event: eventName, data: dataLines.join("\n") });
      }
      eventName = null;
      dataLines = [];
      return;
    }
    if (line.startsWith(":")) return;

    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);

    if (field === "event") eventName = value === "" ? null : value;
    else if (field === "data") dataLines.push(value);
  }

  return {
    push(chunk) {
      const text = decoder.decode(chunk, { stream: true });
      const messages: SseMessage[] = [];
      if (text === "") return messages;

      let lineStart = 0;
      if (skipLineFeed) {
        if (text.charCodeAt(0) === 10) lineStart = 1;
        skipLineFeed = false;
      }

      for (let index = lineStart; index < text.length; index += 1) {
        const char = text.charCodeAt(index);
        if (char !== 10 && char !== 13) continue;

        consumeLine(partialLine + text.slice(lineStart, index), messages);
        partialLine = "";
        if (char === 13) {
          // A CR ends the line at once, so a split CRLF cannot delay an event.
          if (index + 1 === text.length) skipLineFeed = true;
          else if (text.charCodeAt(index + 1) === 10) index += 1;
        }
        lineStart = index + 1;
      }
      partialLine += text.slice(lineStart);
      return messages;
    },
  };
}

/**
 * Decode one block. The backend sends `type` on the `event:` line only,
 * so this function adds it. All other fields stay unchanged.
 */
export function decodeSseEvent<E extends SseEventBase = UnknownSseEvent>(
  message: SseMessage,
): E {
  let data: unknown;
  try {
    data = JSON.parse(message.data);
  } catch (cause) {
    throw failure("stream_invalid_event", cause);
  }
  if (!isRecord(data)) throw failure("stream_invalid_event");

  const type =
    message.event ?? (typeof data.type === "string" ? data.type : "message");
  return { ...data, type } as unknown as E;
}
