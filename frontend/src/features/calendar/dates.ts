import type { CalendarEntry } from "@/lib/api";

/** All calendar dates show and compute in Vienna time, like the appointment card. */
export const TIME_ZONE = "Europe/Vienna";

const pad = (value: number) => String(value).padStart(2, "0");
const keyFormat = new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit" });
const partsFormat = new Intl.DateTimeFormat("en-US", {
  timeZone: TIME_ZONE, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
});

/** `YYYY-MM-DD` of an instant in Vienna. */
export function dayKey(value: Date | string): string {
  return keyFormat.format(typeof value === "string" ? new Date(value) : value);
}

export function keyOf(year: number, monthIndex: number, day: number): string {
  return `${year}-${pad(monthIndex + 1)}-${pad(day)}`;
}

function viennaOffsetMinutes(utcMs: number): number {
  const parts = Object.fromEntries(partsFormat.formatToParts(new Date(utcMs)).map((part) => [part.type, Number(part.value)]));
  return (Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute) - utcMs) / 60_000;
}

/** Turn a Vienna wall-clock date (`YYYY-MM-DD`) and time (`HH:MM`) into an ISO instant with offset. */
export function viennaInstant(date: string, time = "00:00"): string {
  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  const naive = Date.UTC(year, month - 1, day, hour, minute);
  let instant = naive - viennaOffsetMinutes(naive) * 60_000;
  // A second pass corrects the offset on the two daylight-saving switch days.
  instant = naive - viennaOffsetMinutes(instant) * 60_000;
  return new Date(instant).toISOString();
}

/** An entry is upcoming until its end. All-day entries stay upcoming for the whole day. */
export function isUpcoming(entry: CalendarEntry, now = new Date()): boolean {
  if (entry.all_day) return dayKey(entry.start) >= dayKey(now);
  return Date.parse(entry.end ?? entry.start) >= now.getTime();
}

const time = new Intl.DateTimeFormat("de-AT", { hour: "2-digit", minute: "2-digit", timeZone: TIME_ZONE });

export function formatTime(entry: CalendarEntry): string {
  if (entry.all_day) return "Ganztägig";
  const start = time.format(new Date(entry.start));
  return entry.end ? `${start}–${time.format(new Date(entry.end))} Uhr` : `${start} Uhr`;
}

export const weekdayShort = new Intl.DateTimeFormat("de-AT", { weekday: "short", timeZone: TIME_ZONE });
export const monthShort = new Intl.DateTimeFormat("de-AT", { month: "short", timeZone: TIME_ZONE });
export const dayNumber = new Intl.DateTimeFormat("de-AT", { day: "numeric", timeZone: TIME_ZONE });
export const longDay = new Intl.DateTimeFormat("de-AT", { weekday: "long", day: "numeric", month: "long", timeZone: TIME_ZONE });
export const monthTitle = new Intl.DateTimeFormat("de-AT", { month: "long", year: "numeric", timeZone: "UTC" });

export type MonthCell = { key: string; day: number } | null;

/** Monday-first grid of one month. `null` fills the days before the 1st. */
export function monthGrid(year: number, monthIndex: number): MonthCell[] {
  const first = new Date(Date.UTC(year, monthIndex, 1));
  const lead = (first.getUTCDay() + 6) % 7;
  const days = new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate();
  return [
    ...Array.from({ length: lead }, () => null),
    ...Array.from({ length: days }, (_, index) => ({ key: keyOf(year, monthIndex, index + 1), day: index + 1 })),
  ];
}
