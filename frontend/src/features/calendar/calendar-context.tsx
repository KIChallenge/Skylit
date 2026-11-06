"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { api, type ApiClient, type CalendarEntry, type CalendarEntryCreate } from "@/lib/api";

export type CalendarStatus = "loading" | "ready" | "error";

export type CalendarStore = {
  entries: CalendarEntry[];
  status: CalendarStatus;
  /** The conversation that new manual entries belong to. */
  conversationId?: string;
  reload: () => void;
  /** Resolves with the saved entry. Rejects with a transport error; callers show a German message. */
  add: (entry: CalendarEntryCreate) => Promise<CalendarEntry>;
  remove: (entryId: string) => Promise<void>;
};

const CalendarContext = createContext<CalendarStore | null>(null);

const byStart = (a: CalendarEntry, b: CalendarEntry) => Date.parse(a.start) - Date.parse(b.start);

/** Loads the calendar of the logged-in user once and shares it with the panel and the cards. */
export function CalendarProvider({ children, conversationId, apiClient = api }: {
  children: ReactNode; conversationId?: string; apiClient?: ApiClient;
}) {
  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [status, setStatus] = useState<CalendarStatus>("loading");
  const [attempt, setAttempt] = useState(0);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    const request = new AbortController();
    // A failed call never crashes the page: sync and async failures both end in the error state.
    Promise.resolve().then(() => apiClient.listCalendarEntries({ signal: request.signal })).then((loaded) => {
      if (!alive.current) return;
      setEntries([...loaded].sort(byStart));
      setStatus("ready");
    }, () => {
      if (alive.current && !request.signal.aborted) setStatus("error");
    });
    return () => { alive.current = false; request.abort(); };
  }, [apiClient, attempt]);

  const reload = useCallback(() => { setStatus("loading"); setAttempt((value) => value + 1); }, []);

  const add = useCallback(async (entry: CalendarEntryCreate) => {
    const saved = await apiClient.createCalendarEntry(entry);
    if (alive.current) setEntries((current) => [...current.filter((item) => item.id !== saved.id), saved].sort(byStart));
    return saved;
  }, [apiClient]);

  const remove = useCallback(async (entryId: string) => {
    await apiClient.deleteCalendarEntry(entryId);
    if (alive.current) setEntries((current) => current.filter((item) => item.id !== entryId));
  }, [apiClient]);

  const store = useMemo(() => ({ entries, status, conversationId, reload, add, remove }),
    [entries, status, conversationId, reload, add, remove]);
  return <CalendarContext.Provider value={store}>{children}</CalendarContext.Provider>;
}

/** `null` outside a CalendarProvider, e.g. in the styleguide. Callers then hide calendar actions. */
export function useCalendar(): CalendarStore | null {
  return useContext(CalendarContext);
}
