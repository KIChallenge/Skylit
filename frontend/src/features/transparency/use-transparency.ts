"use client";

import { useEffect, useState } from "react";
import { api, TransportError, type ApiClient, type MessageTransparency } from "@/lib/api";

export type TransparencyState =
  | { status: "loading" }
  | { status: "ready"; data: MessageTransparency }
  | { status: "empty" }
  | { status: "error" };

export type TransparencyResource = {
  state: TransparencyState;
  retry: () => void;
};

// Keep persisted metadata per client and message. Never share data between injected clients.
const cache = new WeakMap<ApiClient, Map<string, TransparencyState>>();
const loading: TransparencyState = { status: "loading" };

export function useTransparency(
  messageId: string | null | undefined,
  client: ApiClient = api,
  enabled = true,
): TransparencyResource {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{
    id: string; client: ApiClient; attempt: number; state: TransparencyState;
  }>();

  useEffect(() => {
    if (!messageId || !enabled) return;
    const controller = new AbortController();
    let clientCache = cache.get(client);
    if (!clientCache) {
      clientCache = new Map();
      cache.set(client, clientCache);
    }
    const saved = clientCache.get(messageId);
    if (saved) return;

    const publish = (state: TransparencyState) => {
      if (controller.signal.aborted) return;
      if (state.status === "ready" || state.status === "empty") clientCache.set(messageId, state);
      setResult({ id: messageId, client, attempt, state });
    };
    // The client supplies the configured timeout. Also ignore clients which cannot abort their promise.
    void Promise.resolve().then(() => {
      if (controller.signal.aborted) return;
      return client.getTransparency(messageId, { signal: controller.signal });
    }).then((data) => {
      if (data) publish({ status: "ready", data });
    }).catch((error: unknown) => {
      publish(error instanceof TransportError && error.status === 404
        ? { status: "empty" } : { status: "error" });
    });
    return () => controller.abort();
  }, [messageId, client, attempt, enabled]);

  const saved = messageId ? cache.get(client)?.get(messageId) : undefined;
  const current = result && result.id === messageId && result.client === client && result.attempt === attempt
    ? result.state : loading;
  return { state: saved ?? current, retry: () => setAttempt((value) => value + 1) };
}
