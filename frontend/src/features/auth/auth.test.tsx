import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { api, type ApiClient, type Persona } from "@/lib/api";
import { demoClient, demoMe, demoPersonas } from "./demo-client";
import { PersonaLogin } from "./persona-login";
import { PersonaMenu } from "./persona-menu";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { listPersonas: vi.fn(), login: vi.fn(), logout: vi.fn() } };
});

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", { writable: true, value: vi.fn().mockImplementation(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn(), addListener: vi.fn(), removeListener: vi.fn() })) });
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);

function client(overrides: Partial<ApiClient> = {}): ApiClient {
  return { ...demoClient, listPersonas: vi.fn().mockResolvedValue(demoPersonas), login: vi.fn().mockImplementation(async (id: string) => demoMe(id)), logout: vi.fn().mockResolvedValue(undefined), ...overrides };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe("PersonaLogin", () => {
  it("shows loading before the API returns the seed personas", async () => {
    const request = deferred<Persona[]>();
    const injected = client({ listPersonas: vi.fn().mockReturnValue(request.promise) });
    render(<PersonaLogin client={injected} onAuthenticated={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("Demo-Personas werden geladen…");
    expect(screen.queryByRole("button", { name: /Als Maria/ })).not.toBeInTheDocument();
    await act(async () => request.resolve(demoPersonas));
    for (const persona of demoPersonas) {
      expect(screen.getByRole("button", { name: `Als ${persona.display_name} anmelden` })).toBeEnabled();
      await waitFor(() => expect(screen.getByText(persona.tagline)).toBeVisible());
    }
    expect(screen.getByText(/Alle Personen und ihre Angaben sind erfunden/)).toBeVisible();
    expect(screen.getByText(/Sie nutzen einen KI-Assistenten/)).toBeVisible();
  });

  it("uses the shared API when no client is injected", async () => {
    const list = vi.spyOn(api, "listPersonas").mockResolvedValue(demoPersonas);
    const login = vi.spyOn(api, "login").mockResolvedValue(demoMe("maria"));
    const authenticated = vi.fn();
    render(<PersonaLogin onAuthenticated={authenticated} />);
    await userEvent.click(await screen.findByRole("button", { name: "Als Maria Berger anmelden" }));
    expect(list).toHaveBeenCalledOnce();
    expect(login).toHaveBeenCalledWith("maria");
    expect(authenticated).toHaveBeenCalledWith(demoMe("maria"));
  });

  it.each(demoPersonas)("authenticates $display_name and blocks concurrent selection", async (persona) => {
    const request = deferred<ReturnType<typeof demoMe>>();
    const injected = client({ login: vi.fn().mockReturnValue(request.promise) });
    const authenticated = vi.fn();
    render(<PersonaLogin client={injected} onAuthenticated={authenticated} />);
    await userEvent.click(await screen.findByRole("button", { name: `Als ${persona.display_name} anmelden` }));
    expect(injected.login).toHaveBeenCalledWith(persona.id);
    expect(authenticated).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Anmeldung läuft…");
    for (const item of demoPersonas) expect(screen.getByRole("button", { name: `Als ${item.display_name} anmelden` })).toBeDisabled();
    await act(async () => request.resolve(demoMe(persona.id)));
    expect(authenticated).toHaveBeenCalledExactlyOnceWith(demoMe(persona.id));
  });

  it("retries persona loading after a safe error", async () => {
    const injected = client({ listPersonas: vi.fn().mockRejectedValueOnce(new Error("private server detail")).mockResolvedValueOnce(demoPersonas) });
    render(<PersonaLogin client={injected} onAuthenticated={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Die Demo-Personas konnten nicht geladen werden.");
    expect(screen.queryByText("private server detail")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByRole("button", { name: "Als Maria Berger anmelden" })).toBeEnabled();
    expect(injected.listPersonas).toHaveBeenCalledTimes(2);
  });

  it("offers retry when the list is empty", async () => {
    const injected = client({ listPersonas: vi.fn().mockResolvedValueOnce([]).mockResolvedValueOnce(demoPersonas) });
    render(<PersonaLogin client={injected} onAuthenticated={vi.fn()} />);
    expect(await screen.findByText("Keine Demo-Personas verfügbar.")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByRole("button", { name: "Als Maria Berger anmelden" })).toBeEnabled();
  });

  it("shows loading for a new client and ignores the previous client's response", async () => {
    const oldRequest = deferred<Persona[]>();
    const newRequest = deferred<Persona[]>();
    const original = client({ listPersonas: vi.fn().mockReturnValue(oldRequest.promise) });
    const replacement = client({ listPersonas: vi.fn().mockReturnValue(newRequest.promise) });
    const authenticated = vi.fn();
    const { rerender } = render(<PersonaLogin client={original} onAuthenticated={authenticated} />);
    rerender(<PersonaLogin client={replacement} onAuthenticated={authenticated} />);
    await act(async () => oldRequest.resolve(demoPersonas));
    expect(screen.getByRole("status")).toHaveTextContent("Demo-Personas werden geladen…");
    expect(screen.queryByRole("button", { name: /Als Maria/ })).not.toBeInTheDocument();
    await act(async () => newRequest.resolve([demoPersonas[2]]));
    expect(screen.getByRole("button", { name: "Als Elif Yılmaz anmelden" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Als Maria/ })).not.toBeInTheDocument();
  });

  it("never signals success after failed login and retries the selected persona", async () => {
    const injected = client({ login: vi.fn().mockRejectedValueOnce(new Error("secret detail")).mockResolvedValueOnce(demoMe("elif")) });
    const authenticated = vi.fn();
    render(<PersonaLogin client={injected} onAuthenticated={authenticated} />);
    await userEvent.click(await screen.findByRole("button", { name: "Als Elif Yılmaz anmelden" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Die Anmeldung ist fehlgeschlagen.");
    expect(authenticated).not.toHaveBeenCalled();
    expect(screen.queryByText(/erfolgreich/)).not.toBeInTheDocument();
    expect(screen.queryByText("secret detail")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(injected.login).toHaveBeenNthCalledWith(2, "elif");
    expect(authenticated).toHaveBeenCalledExactlyOnceWith(demoMe("elif"));
  });

  it("ignores a stale list response after unmount", async () => {
    const request = deferred<Persona[]>();
    const injected = client({ listPersonas: vi.fn().mockReturnValue(request.promise) });
    const { unmount } = render(<PersonaLogin client={injected} onAuthenticated={vi.fn()} />);
    const options = vi.mocked(injected.listPersonas).mock.calls[0][0];
    unmount();
    expect(options?.signal?.aborted).toBe(true);
    await act(async () => request.resolve(demoPersonas));
  });

  it("supports persona selection with the keyboard", async () => {
    const authenticated = vi.fn();
    const user = userEvent.setup();
    render(<PersonaLogin client={client()} onAuthenticated={authenticated} />);
    const maria = await screen.findByRole("button", { name: "Als Maria Berger anmelden" });
    await user.tab();
    expect(maria).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(authenticated).toHaveBeenCalledExactlyOnceWith(demoMe("maria"));
  });

  it("does not authenticate a removed view after a pending login completes", async () => {
    const request = deferred<ReturnType<typeof demoMe>>();
    const authenticated = vi.fn();
    const injected = client({ login: vi.fn().mockReturnValue(request.promise) });
    const { unmount } = render(<PersonaLogin client={injected} onAuthenticated={authenticated} />);
    await userEvent.click(await screen.findByRole("button", { name: "Als Maria Berger anmelden" }));
    unmount();
    await act(async () => request.resolve(demoMe("maria")));
    expect(authenticated).not.toHaveBeenCalled();
  });
});

describe("PersonaMenu", () => {
  it("shows the simulated SV data with a masked number, badge and source", async () => {
    render(<PersonaMenu me={demoMe("elif")} client={client()} onLoggedOut={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Persona-Menü: Elif Yılmaz" }));
    const panel = await screen.findByRole("region", { name: "Meine Daten" });
    expect(panel).toHaveTextContent("•••• ••0995");
    expect(panel).not.toHaveTextContent("7898110995");
    expect(panel).toHaveTextContent("Demo-Daten");
    expect(panel).toHaveTextContent("Quelle: simulierte SV-Datenabfrage · Stand 06.11.2026");
    expect(panel).toHaveTextContent("Mustergasse 3, 1160 Wien");
    expect(panel).toHaveTextContent("Deniz Yılmaz (Kind, geb. 18.03.2024)");
  });

  it("uses the shared API for logout when no client is injected", async () => {
    const logout = vi.spyOn(api, "logout").mockResolvedValue(undefined);
    const loggedOut = vi.fn();
    render(<PersonaMenu me={demoMe("elif")} onLoggedOut={loggedOut} />);
    await userEvent.click(screen.getByRole("button", { name: "Persona-Menü: Elif Yılmaz" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Abmelden" }));
    expect(logout).toHaveBeenCalledOnce();
    expect(loggedOut).toHaveBeenCalledOnce();
  });

  it("closes on Escape and restores focus without logging out", async () => {
    const injected = client();
    const user = userEvent.setup();
    render(<PersonaMenu me={demoMe("maria")} client={injected} onLoggedOut={vi.fn()} />);
    const trigger = screen.getByRole("button", { name: "Persona-Menü: Maria Berger" });
    await user.tab();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("menu")).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(injected.logout).not.toHaveBeenCalled();
  });

  it("supports keyboard opening and logout with pending feedback", async () => {
    const request = deferred<void>();
    const injected = client({ logout: vi.fn().mockReturnValue(request.promise) });
    const loggedOut = vi.fn();
    const user = userEvent.setup();
    render(<PersonaMenu me={demoMe("maria")} client={injected} onLoggedOut={loggedOut} />);
    await user.tab();
    expect(screen.getByRole("button", { name: "Persona-Menü: Maria Berger" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("menu")).toBeVisible();
    expect(screen.getByText("Synthetische Demo-Persona")).toBeVisible();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(injected.logout).toHaveBeenCalledOnce());
    expect(loggedOut).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Abmeldung läuft…");
    expect(screen.getByRole("menuitem")).toHaveAttribute("aria-disabled", "true");
    await act(async () => request.resolve());
    expect(loggedOut).toHaveBeenCalledOnce();
  });

  it("keeps the session after failed logout and provides retry", async () => {
    const injected = client({ logout: vi.fn().mockRejectedValueOnce(new Error("private detail")).mockResolvedValueOnce(undefined) });
    const loggedOut = vi.fn();
    render(<PersonaMenu me={demoMe("maria")} client={injected} onLoggedOut={loggedOut} />);
    await userEvent.click(screen.getByRole("button", { name: "Persona-Menü: Maria Berger" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Abmelden" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sie sind weiterhin angemeldet.");
    expect(loggedOut).not.toHaveBeenCalled();
    expect(screen.queryByText("private detail")).not.toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Erneut versuchen" })).toBeVisible();
    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(loggedOut).toHaveBeenCalledOnce());
    expect(injected.logout).toHaveBeenCalledTimes(2);
  });
});
