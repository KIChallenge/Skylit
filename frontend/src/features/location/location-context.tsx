"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export type LocationStatus =
  /** Not asked yet, or the browser has not answered. */
  | "idle"
  | "locating"
  | "granted"
  | "denied"
  /** No geolocation API, an insecure origin, a timeout or no position fix. */
  | "unavailable";

export type Coordinates = { lat: number; lon: number };

export type LocationStore = {
  status: LocationStatus;
  /** Rounded to about 100 m. Kept in memory only, never in storage. */
  coords: Coordinates | null;
  /** Opens the browser permission prompt. Resolves with the coordinates or null. */
  request: () => Promise<Coordinates | null>;
  /** The latest coordinates, also inside callbacks created before `request` resolved. */
  current: () => Coordinates | null;
};

/** Remembers only the answer, never a position: "granted" or "dismissed". */
export const LOCATION_CHOICE_KEY = "lotse.location.choice";
const TIMEOUT_MS = 10_000;

const LocationContext = createContext<LocationStore | null>(null);

function readChoice(): string | null {
  try { return localStorage.getItem(LOCATION_CHOICE_KEY); } catch { return null; }
}

export function rememberLocationChoice(choice: "granted" | "dismissed") {
  try { localStorage.setItem(LOCATION_CHOICE_KEY, choice); } catch { /* private mode: ask again next time */ }
}

/** About 100 m precision is enough for a distance ranking and shares less. */
const round = (value: number) => Math.round(value * 1000) / 1000;

export function LocationProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<LocationStatus>("idle");
  const [coords, setCoords] = useState<Coordinates | null>(null);
  const alive = useRef(true);
  const pending = useRef<Promise<Coordinates | null> | null>(null);
  const latest = useRef<Coordinates | null>(null);
  const current = useCallback(() => latest.current, []);

  const request = useCallback(() => {
    if (pending.current) return pending.current;
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
      setStatus("unavailable");
      return Promise.resolve(null);
    }
    setStatus("locating");
    pending.current = new Promise<Coordinates | null>((resolve) => {
      navigator.geolocation.getCurrentPosition((position) => {
        const next = { lat: round(position.coords.latitude), lon: round(position.coords.longitude) };
        rememberLocationChoice("granted");
        latest.current = next;
        if (alive.current) { setCoords(next); setStatus("granted"); }
        resolve(next);
      }, (error) => {
        if (error.code === error.PERMISSION_DENIED) rememberLocationChoice("dismissed");
        if (alive.current) setStatus(error.code === error.PERMISSION_DENIED ? "denied" : "unavailable");
        resolve(null);
      }, { enableHighAccuracy: false, timeout: TIMEOUT_MS, maximumAge: 5 * 60_000 });
    }).finally(() => { pending.current = null; });
    return pending.current;
  }, []);

  useEffect(() => {
    alive.current = true;
    // A person who allowed it before gets the position without a new prompt.
    if (readChoice() === "granted") {
      void navigator.permissions?.query({ name: "geolocation" }).then((result) => {
        if (alive.current && result.state === "granted") void request();
      }, () => {});
    }
    return () => { alive.current = false; };
  }, [request]);

  const store = useMemo(() => ({ status, coords, request, current }), [status, coords, request, current]);
  return <LocationContext.Provider value={store}>{children}</LocationContext.Provider>;
}

/** `null` outside a LocationProvider, e.g. in the styleguide. */
export function useLocation(): LocationStore | null {
  return useContext(LocationContext);
}

/** True when the app should explain and offer location sharing once. */
export async function shouldOfferLocation(): Promise<boolean> {
  if (typeof navigator === "undefined" || !("geolocation" in navigator)) return false;
  if (readChoice()) return false;
  try {
    const result = await navigator.permissions?.query({ name: "geolocation" });
    return !result || result.state === "prompt";
  } catch {
    return true;
  }
}
