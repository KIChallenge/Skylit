import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

import { formatAppointment, formatDistance } from "./provider-cards";
import { ResultCard } from "./result-cards";

const wolkenfeld = {
  id: "gp-1030", name: "Demo-Ordination Dr. Nora Wolkenfeld", kind: "gp", specialty: null,
  address: "Demogasse 1", postal_code: "1030", distance_km: 0.04, phone: "+43 1 000 10 30", demo: true,
};
const kieselstern = {
  id: "gp-1100", name: "Demo-Ordination Dr. Emil Kieselstern", kind: "gp", specialty: null,
  address: "Beispielweg 2", postal_code: "1100", distance_km: 3.456, phone: null, demo: true,
};

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://backend.example");
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("provider card", () => {
  it("lists providers nearest first with distance, type, address and phone", () => {
    render(<ResultCard card={{ type: "provider_list", providers: [wolkenfeld, kieselstern], demo: true }} />);
    expect(screen.getByRole("heading", { name: "Anbieter in Ihrer Nähe" })).toBeInTheDocument();
    expect(screen.getByText("Demo-Daten")).toBeInTheDocument();
    const items = within(screen.getByRole("list", { name: "Anbieter, nächster zuerst" })).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText("unter 100 m")).toBeInTheDocument();
    expect(within(items[1]).getByText("ca. 3,5 km")).toBeInTheDocument();
    expect(within(items[0]).getAllByText(/Allgemeinmedizin/).length).toBeGreaterThan(0);
    expect(within(items[0]).getByText("Demogasse 1, 1030 Wien")).toBeInTheDocument();
    expect(within(items[0]).getByRole("link", { name: /anrufen/ })).toHaveAttribute("href", "tel:+4310001030");
    // No phone number, no call button.
    expect(within(items[1]).queryByRole("link", { name: /anrufen/ })).not.toBeInTheDocument();
    // Without a send handler the follow-up actions stay hidden.
    expect(screen.queryByRole("button", { name: /Termin vorschlagen/ })).not.toBeInTheDocument();
  });

  it("sends follow-up requests for a provider as chat messages", () => {
    const onSend = vi.fn();
    render(<ResultCard card={{ type: "provider_list", providers: [wolkenfeld], demo: true }} onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: /Termin vorschlagen/ }));
    expect(onSend).toHaveBeenLastCalledWith("Bitte schlagen Sie mir einen Termin bei Demo-Ordination Dr. Nora Wolkenfeld vor.");
    fireEvent.click(screen.getByRole("button", { name: /E-Mail entwerfen/ }));
    expect(onSend).toHaveBeenLastCalledWith("Bitte entwerfen Sie eine E-Mail an Demo-Ordination Dr. Nora Wolkenfeld.");
  });

  it("shows a calm empty state when nothing matches", () => {
    render(<ResultCard card={{ type: "provider_list", providers: [], demo: true }} />);
    expect(screen.getByText("Keine passenden Anbieter gefunden.")).toBeInTheDocument();
  });
});

describe("appointment card", () => {
  it("shows the proposal in Vienna time with a calendar download and a booking hint", () => {
    render(<ResultCard card={{
      type: "appointment", demo: true,
      appointment: { id: "a1", start: "2026-11-10T08:00:00Z", end: "2026-11-10T08:45:00Z", ics_url: "/api/appointments/a1/ics", provider: wolkenfeld, demo: true },
    }} />);
    expect(screen.getByRole("heading", { name: "Terminvorschlag" })).toBeInTheDocument();
    expect(screen.getByText("Dienstag, 10. November 2026, 09:00–09:45 Uhr")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Als \.ics herunterladen/ })).toBeInTheDocument();
    expect(screen.getByText(/keine Buchung/)).toBeInTheDocument();
    expect(screen.getByText("Demo-Daten")).toBeInTheDocument();
  });

  it("formats distances and keeps invalid dates readable", () => {
    expect(formatDistance(null)).toBeNull();
    expect(formatDistance(1.25)).toBe("ca. 1,3 km");
    expect(formatAppointment("kaputt", "auch")).toBe("kaputt – auch");
  });
});

describe("provider type label", () => {
  it("drops a specialty that repeats the type", async () => {
    const { providerKind } = await import("./provider-cards");
    expect(providerKind({ kind: "gp", specialty: "Allgemeinmedizin" })).toBe("Allgemeinmedizin");
    expect(providerKind({ kind: "therapy", specialty: "Physiotherapie" })).toBe("Therapie · Physiotherapie");
  });
});
