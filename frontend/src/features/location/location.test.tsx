import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProviderListCard } from "@/features/cards/provider-cards";
import type { CardOf } from "@/lib/api";

import { LocationDialog, LocationProvider, useLocation } from ".";
import { LOCATION_CHOICE_KEY, type LocationStore } from "./location-context";

const getCurrentPosition = vi.fn();

function stubBrowser(state: PermissionState = "prompt") {
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: { getCurrentPosition } });
  Object.defineProperty(navigator, "permissions", {
    configurable: true, value: { query: vi.fn().mockResolvedValue({ state }) },
  });
}

function Coords() {
  const location = useLocation();
  return <p data-testid="coords">{location?.coords ? `${location.coords.lat},${location.coords.lon}` : location?.status}</p>;
}

// Node 26 ships its own global localStorage, which hides the jsdom one. Use a fresh store.
const items = new Map<string, string>();
beforeEach(() => {
  items.clear();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, String(value)),
    removeItem: (key: string) => void items.delete(key),
    clear: () => items.clear(),
  });
  getCurrentPosition.mockReset();
  stubBrowser();
});
afterEach(cleanup);

describe("LocationDialog", () => {
  it("explains first, then opens the browser prompt and keeps rounded coordinates in memory", async () => {
    const user = userEvent.setup();
    getCurrentPosition.mockImplementation((ok) => ok({ coords: { latitude: 48.208176, longitude: 16.373819 } }));
    render(<LocationProvider><LocationDialog /><Coords /></LocationProvider>);
    expect(await screen.findByRole("dialog", { name: "Standort für genauere Entfernungen?" })).toBeInTheDocument();
    expect(getCurrentPosition).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Standort freigeben" }));
    expect(getCurrentPosition).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.getByTestId("coords")).toHaveTextContent("48.208,16.374"));
    expect(localStorage.getItem(LOCATION_CHOICE_KEY)).toBe("granted");
    expect([...items.values()].join()).not.toContain("48.2");
  });

  it("gives callbacks from before the prompt the new coordinates", async () => {
    getCurrentPosition.mockImplementation((ok) => ok({ coords: { latitude: 48.2, longitude: 16.4 } }));
    let first: LocationStore | null = null;
    function Capture() {
      const location = useLocation();
      first ??= location;
      return null;
    }
    render(<LocationProvider><Capture /></LocationProvider>);
    const store = first as LocationStore | null;
    if (!store) throw new Error("no location store");
    await act(() => store.request());
    expect(store.coords).toBeNull();
    expect(store.current()).toEqual({ lat: 48.2, lon: 16.4 });
  });

  it("asks only once after „Nicht jetzt“", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<LocationProvider><LocationDialog /></LocationProvider>);
    await user.click(await screen.findByRole("button", { name: "Nicht jetzt" }));
    expect(getCurrentPosition).not.toHaveBeenCalled();
    expect(localStorage.getItem(LOCATION_CHOICE_KEY)).toBe("dismissed");
    unmount();
    render(<LocationProvider><LocationDialog /></LocationProvider>);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("stays closed when the browser already decided", async () => {
    stubBrowser("denied");
    render(<LocationProvider><LocationDialog /></LocationProvider>);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("ProviderListCard with open data", () => {
  const card = (origin: "postal_code" | "location") => ({
    type: "provider_list", demo: false, origin,
    providers: [{
      id: "wien-arzt-1", name: "Dr. Beispiel", kind: "specialist", specialty: "Innere Medizin u. Kardiologie",
      address: "Beispielgasse 1, 1030 Wien", postal_code: "1030", distance_km: 0.4, phone: null,
      website: "https://praxisplan.at/1/beispiel/ordination/1", demo: false,
    }],
  }) as unknown as CardOf<"provider_list">;

  it("labels the source, links the practice and offers no demo appointment", () => {
    render(<LocationProvider><ProviderListCard card={card("postal_code")} onSend={vi.fn()} /></LocationProvider>);
    expect(screen.getByText("Offene Daten Stadt Wien")).toBeInTheDocument();
    expect(screen.queryByText("Demo-Daten")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Termin vorschlagen/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ordinationsseite/ })).toHaveAttribute("href", "https://praxisplan.at/1/beispiel/ordination/1");
    expect(screen.getByText(/Kassenvertrag und Öffnungszeiten stehen nicht darin/)).toBeInTheDocument();
    expect(screen.getByText("Die Entfernung ist eine Luftlinie ab Ihrer Postleitzahl.")).toBeInTheDocument();
  });

  it("re-searches from the shared location on request", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    getCurrentPosition.mockImplementation((ok) => ok({ coords: { latitude: 48.2, longitude: 16.4 } }));
    render(<LocationProvider><ProviderListCard card={card("postal_code")} onSend={onSend} /></LocationProvider>);
    await user.click(screen.getByRole("button", { name: "Mit meinem Standort genauer suchen" }));
    await waitFor(() => expect(onSend).toHaveBeenCalledWith("Bitte suchen Sie die Anbieter noch einmal ab meinem Standort."));
  });

  it("names the location as the distance origin", () => {
    render(<LocationProvider><ProviderListCard card={card("location")} onSend={vi.fn()} /></LocationProvider>);
    expect(screen.getByText("Die Entfernung ist eine Luftlinie ab Ihrem Standort.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Standort genauer/ })).not.toBeInTheDocument();
  });
});
