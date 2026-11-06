import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppointmentCard } from "@/features/cards/provider-cards";
import type { ApiClient, CalendarEntry, CardOf } from "@/lib/api";

import { CalendarPanel, CalendarProvider } from ".";
import { isUpcoming, viennaInstant } from "./dates";

afterEach(cleanup);

const day = 24 * 60 * 60 * 1000;
const inDays = (days: number) => new Date(Date.now() + days * day).toISOString();

function entry(overrides: Partial<CalendarEntry>): CalendarEntry {
  return {
    id: crypto.randomUUID(), kind: "appointment", title: "Kontrolle", start: inDays(1), end: null, all_day: false,
    location: null, note: null, conversation_id: null, appointment_id: null, ...overrides,
  };
}

function client(entries: CalendarEntry[], overrides: Partial<ApiClient> = {}) {
  return {
    listCalendarEntries: vi.fn().mockResolvedValue(entries),
    createCalendarEntry: vi.fn(),
    deleteCalendarEntry: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as unknown as ApiClient;
}

function setup(apiClient: ApiClient) {
  return render(<CalendarProvider apiClient={apiClient} conversationId="conv-1"><CalendarPanel /></CalendarProvider>);
}

describe("dates", () => {
  it("converts Vienna wall-clock time in winter and summer", () => {
    expect(viennaInstant("2026-01-15", "09:30")).toBe("2026-01-15T08:30:00.000Z");
    expect(viennaInstant("2026-07-15", "09:30")).toBe("2026-07-15T07:30:00.000Z");
  });

  it("keeps all-day entries upcoming for the whole day", () => {
    const now = new Date("2026-11-06T20:00:00Z");
    expect(isUpcoming(entry({ all_day: true, start: viennaInstant("2026-11-06") }), now)).toBe(true);
    expect(isUpcoming(entry({ start: "2026-11-06T08:00:00Z" }), now)).toBe(false);
  });
});

describe("CalendarPanel", () => {
  it("shows the next three upcoming dates when minimized and hides past ones", async () => {
    const entries = [
      entry({ title: "Vergangen", start: inDays(-2) }),
      ...[1, 2, 3, 4].map((offset) => entry({ title: `Termin ${offset}`, start: inDays(offset) })),
    ];
    setup(client(entries));
    const list = await screen.findByRole("list", { name: "Nächste Termine" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.queryByText("Vergangen")).not.toBeInTheDocument();
    expect(screen.getByText("4 bevorstehend")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "1 weiterer Termin" })).toBeInTheDocument();
  });

  it("maximizes to show all dates, deletes one and minimizes with Escape", async () => {
    const user = userEvent.setup();
    const entries = [1, 2, 3, 4].map((offset) => entry({ title: `Termin ${offset}`, start: inDays(offset) }));
    const api = client(entries);
    const { container } = setup(api);
    await user.click(await screen.findByRole("button", { name: "Kalender vergrößern" }));
    expect(container.querySelector("[data-calendar=expanded]")).not.toBeNull();
    expect(screen.getByText("Termin 4")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Eintrag löschen: Termin 4" }));
    await waitFor(() => expect(screen.queryByText("Termin 4")).not.toBeInTheDocument());
    expect(api.deleteCalendarEntry).toHaveBeenCalledWith(entries[3].id);
    screen.getByRole("button", { name: "Kalender verkleinern" }).focus();
    await user.keyboard("{Escape}");
    expect(container.querySelector("[data-calendar=collapsed]")).not.toBeNull();
  });

  it("saves a manual all-day entry for the current conversation", async () => {
    const user = userEvent.setup();
    const api = client([], {
      createCalendarEntry: vi.fn().mockImplementation(async (body) => entry({ ...body, id: "new" })),
    });
    setup(api);
    await user.click(await screen.findByRole("button", { name: "Termin eintragen" }));
    await user.type(screen.getByLabelText("Was steht an?"), "Befund abholen");
    await user.click(screen.getByRole("radio", { name: /Frist/ }));
    const date = screen.getByLabelText("Datum");
    await user.clear(date);
    await user.type(date, "2099-03-02");
    await user.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.createCalendarEntry).toHaveBeenCalledWith(expect.objectContaining({
      kind: "deadline", title: "Befund abholen", all_day: true, conversation_id: "conv-1", start: "2099-03-01T23:00:00.000Z",
    })));
    expect(await screen.findByText("Befund abholen")).toBeInTheDocument();
  });

  it("shows a retry when the calendar cannot load", async () => {
    const user = userEvent.setup();
    const api = client([], { listCalendarEntries: vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue([]) });
    setup(api);
    await user.click(await screen.findByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByText("Keine bevorstehenden Termine.")).toBeInTheDocument();
  });
});

describe("AppointmentCard", () => {
  const card = {
    type: "appointment", demo: true,
    appointment: {
      id: "appt-1", start: inDays(2), end: inDays(2), ics_url: "/api/appointments/appt-1/ics", demo: true,
      provider: { id: "p", name: "Demo-Pflegeberatung Morgenblatt", kind: "care_counselling", address: "Demogasse 2, 1030 Wien", phone: null, demo: true },
    },
  } as unknown as CardOf<"appointment">;

  it("saves the proposal into the calendar once", async () => {
    const user = userEvent.setup();
    const api = client([], {
      createCalendarEntry: vi.fn().mockResolvedValue(entry({ appointment_id: "appt-1", title: "Pflegeberatung" })),
    });
    render(<CalendarProvider apiClient={api}><AppointmentCard card={card} /></CalendarProvider>);
    await user.click(await screen.findByRole("button", { name: "Im Kalender speichern" }));
    expect(api.createCalendarEntry).toHaveBeenCalledWith({ appointment_id: "appt-1" });
    expect(await screen.findByText("Im Kalender gespeichert")).toBeInTheDocument();
  });

  it("hides the button without a calendar", () => {
    render(<AppointmentCard card={card} />);
    expect(screen.queryByRole("button", { name: "Im Kalender speichern" })).not.toBeInTheDocument();
  });
});
