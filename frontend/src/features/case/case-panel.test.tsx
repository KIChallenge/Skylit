import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, createApiClient, type ApiClient, type Case, type CaseStep } from "@/lib/api";

import { CasePanel } from "./case-panel";
import { syntheticCase } from "./synthetic-case";

// Animation timing belongs to the shared Enter component, not the case behavior tests.
vi.mock("@/components/ui/enter", () => ({ Enter: ({ children }: { children: ReactNode }) => <div>{children}</div> }));

afterEach(cleanup);

const fixture = (): Case => structuredClone(syntheticCase);
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function setup(client: ApiClient = api, value: Case | null = fixture()) {
  const onCaseChange = vi.fn();
  const onRetry = vi.fn();
  const result = render(<CasePanel case={value} apiClient={client} onCaseChange={onCaseChange} onRetry={onRetry} />);
  return { ...result, onCaseChange, onRetry };
}
function documentStep(value = fixture()) { return value.steps.find((step) => step.id === "step-document")!; }

describe("CasePanel", () => {
  it("sorts steps by position without mutating the supplied case", () => {
    const value = fixture();
    setup(api, value);
    const steps = within(screen.getByRole("list", { name: "Ihre nächsten Schritte" })).getAllByRole("listitem");
    expect(within(steps[0]).getByRole("checkbox")).toHaveAccessibleName("Entlassungsbrief bereithalten");
    expect(within(steps[1]).getByRole("checkbox")).toHaveAccessibleName("Pflegegeldantrag prüfen");
    expect(value.steps[0].position).toBe(2);
    expect(screen.queryByRole("main")).not.toBeInTheDocument();
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });

  it.each([0, 1, 3, 6])("opens only the first unfinished step by position with %i completed steps", async (completed) => {
    const value = fixture();
    const sorted = [...value.steps].sort((a, b) => a.position - b.position);
    sorted.slice(0, completed).forEach((step) => { step.status = "done"; });
    setup(api, value);
    for (const [index, step] of sorted.entries()) {
      expect(screen.getByRole("button", { name: `Details zu „${step.title}“` }))
        .toHaveAttribute("aria-expanded", String(index === completed));
      if (index === completed) {
        expect(screen.getByText(step.description)).toBeVisible();
      } else {
        expect(screen.queryByText(step.description)).not.toBeInTheDocument();
      }
    }
    const details = screen.getByRole("button", { name: `Details zu „${sorted[0].title}“` });
    details.focus();
    await userEvent.keyboard("{Enter}");
    expect(details).toHaveAttribute("aria-expanded", String(completed !== 0));
  });

  it("shows all statuses with symbols, categories, descriptions and due hints", () => {
    const value = fixture();
    value.steps[4].status = "done";
    setup(api, value);
    for (const label of ["Offen", "In Arbeit", "Blockiert", "Erledigt"]) {
      const badge = screen.getAllByText(label)[0];
      expect(badge.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    }
    expect(screen.getByText("Formular")).toBeVisible();
    expect(screen.getByText("Von Ihnen zu prüfen")).toBeVisible();
    expect(screen.getByText(documentStep(value).description)).toBeVisible();
    expect(screen.getByText("Vor dem Beratungsgespräch")).toBeVisible();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuetext", "1 von 6 erledigt");
    expect(screen.getByText("Für: Mutter oder Vater")).toBeVisible();
  });

  it("sends PATCH through the API facade and reports the returned step", async () => {
    const request = deferred<Response>();
    const fetch = vi.fn(() => request.promise);
    const client = createApiClient({ baseUrl: "http://case.test", timeoutMs: 10_000, fetch });
    const { onCaseChange } = setup(client);
    const checkbox = screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" });
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
    expect(checkbox).toBeDisabled();
    expect(screen.getByText("Änderung wird gespeichert…")).toBeVisible();
    fireEvent.click(checkbox);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]).toEqual(["http://case.test/api/case-steps/step-document", expect.objectContaining({
      method: "PATCH", body: JSON.stringify({ status: "done" }), credentials: "include",
    })]);
    const saved = { ...documentStep(), status: "done" as const, description: "Vom Server bestätigte Beschreibung." };
    await act(async () => request.resolve(new Response(JSON.stringify(saved), { headers: { "Content-Type": "application/json" } })));
    await waitFor(() => expect(onCaseChange).toHaveBeenCalledOnce());
    expect(onCaseChange.mock.calls[0][0].steps.find((step: CaseStep) => step.id === saved.id)).toEqual(saved);
    expect(checkbox).toBeEnabled();
    expect(screen.getByText(saved.description)).toBeVisible();
    expect(screen.getByText("1 von 6 erledigt")).toBeVisible();
  });

  it("rolls back failed updates and retries the same intended status", async () => {
    const request = deferred<CaseStep>();
    const updateCaseStep = vi.fn().mockImplementationOnce(() => request.promise)
      .mockResolvedValueOnce({ ...documentStep(), status: "done" });
    const { onCaseChange } = setup({ ...api, updateCaseStep });
    const checkbox = screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" });
    fireEvent.click(checkbox);
    await act(async () => request.reject(new Error("Private server details")));
    expect(checkbox).not.toBeChecked();
    expect(checkbox).toBeEnabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Änderung nicht gespeichert.");
    expect(screen.queryByText("Private server details")).not.toBeInTheDocument();
    expect(onCaseChange).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    await waitFor(() => expect(onCaseChange).toHaveBeenCalledOnce());
    expect(updateCaseStep).toHaveBeenNthCalledWith(2, "step-document", "done");
    expect(checkbox).toBeChecked();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("restores in-progress status after a failed form update", async () => {
    setup({ ...api, updateCaseStep: vi.fn().mockRejectedValue(new Error("failure")) });
    fireEvent.click(screen.getByRole("checkbox", { name: "Pflegegeldantrag prüfen" }));
    await screen.findByRole("alert");
    expect(screen.getByText("In Arbeit")).toBeVisible();
    expect(screen.getByText("Von Ihnen zu prüfen")).toBeVisible();
  });

  it("allows repeated toggles before the parent acknowledges an update", async () => {
    const updateCaseStep = vi.fn(async (_id, status) => ({ ...documentStep(), status }));
    const { onCaseChange } = setup({ ...api, updateCaseStep });
    const checkbox = screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" });
    await userEvent.click(checkbox);
    await waitFor(() => expect(onCaseChange).toHaveBeenCalledTimes(1));
    await userEvent.click(checkbox);
    await waitFor(() => expect(onCaseChange).toHaveBeenCalledTimes(2));
    expect(checkbox).not.toBeChecked();
    expect(screen.getByText("0 von 6 erledigt")).toBeVisible();
  });

  it("keeps concurrent steps independent and reports only confirmed changes", async () => {
    const first = deferred<CaseStep>();
    const second = deferred<CaseStep>();
    const value = fixture();
    const form = value.steps[0];
    const updateCaseStep = vi.fn((id) => id === "step-document" ? first.promise : second.promise);
    const { onCaseChange } = setup({ ...api, updateCaseStep }, value);
    fireEvent.click(screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Pflegegeldantrag prüfen" }));
    await act(async () => first.resolve({ ...documentStep(value), status: "done" }));
    expect(onCaseChange.mock.calls[0][0].steps.find((step: CaseStep) => step.id === form.id).status).toBe("in_progress");
    await act(async () => second.reject(new Error("failure")));
    expect(screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Pflegegeldantrag prüfen" })).not.toBeChecked();
    expect(screen.getByText("1 von 6 erledigt")).toBeVisible();
  });

  it("merges successful changes into the latest supplied case", async () => {
    const request = deferred<CaseStep>();
    const onCaseChange = vi.fn();
    const client = { ...api, updateCaseStep: vi.fn(() => request.promise) };
    const value = fixture();
    const props = { apiClient: client, onCaseChange, onRetry: vi.fn() };
    const { rerender } = render(<CasePanel {...props} case={value} />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" }));
    const incoming = { ...value, title: "Aktualisierter Fall", steps: [...value.steps, { ...value.steps[0], id: "new", position: 7 }] };
    rerender(<CasePanel {...props} case={incoming} />);
    await act(async () => request.resolve({ ...documentStep(value), status: "done" }));
    expect(onCaseChange.mock.calls[0][0].title).toBe(incoming.title);
    expect(onCaseChange.mock.calls[0][0].steps).toHaveLength(7);
  });

  it("ignores old requests when the page switches to another case", async () => {
    const request = deferred<CaseStep>();
    const { rerender, onCaseChange, onRetry } = setup({ ...api, updateCaseStep: vi.fn(() => request.promise) });
    fireEvent.click(screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" }));
    rerender(<CasePanel case={{ ...fixture(), id: "different-case" }} onCaseChange={onCaseChange} onRetry={onRetry} />);
    await act(async () => request.resolve({ ...documentStep(), status: "done" }));
    expect(onCaseChange).not.toHaveBeenCalled();
    expect(screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" })).not.toBeChecked();
  });

  it("uses authoritative incoming case data after a completed update", async () => {
    const value = fixture();
    const updateCaseStep = vi.fn(async (_id, status) => ({ ...documentStep(value), status }));
    const { rerender, onCaseChange, onRetry } = setup({ ...api, updateCaseStep }, value);
    await userEvent.click(screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" }));
    await waitFor(() => expect(onCaseChange).toHaveBeenCalledOnce());
    expect(screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" })).toBeChecked();
    rerender(<CasePanel case={fixture()} apiClient={{ ...api, updateCaseStep }} onCaseChange={onCaseChange} onRetry={onRetry} />);
    expect(screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" })).not.toBeChecked();
  });

  it("shows loading, empty, and safe error states with retry", async () => {
    const onRetry = vi.fn();
    const props = { case: null, onCaseChange: vi.fn(), onRetry };
    const { rerender } = render(<CasePanel {...props} isLoading />);
    expect(screen.getByRole("status")).toHaveTextContent("Mein Fall wird geladen…");
    rerender(<CasePanel {...props} />);
    expect(screen.getByText("Noch keine Schritte.")).toBeVisible();
    rerender(<CasePanel {...props} error={new Error("Secret error")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Ihr Fall konnte nicht geladen werden.");
    expect(screen.queryByText("Secret error")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("expands the summary and supports keyboard toggling", async () => {
    const updateCaseStep = vi.fn(async (_id, status) => ({ ...documentStep(), status }));
    setup({ ...api, updateCaseStep });
    await userEvent.click(screen.getByRole("button", { name: "Ganze Zusammenfassung" }));
    expect(screen.getByText(syntheticCase.summary)).toBeVisible();
    const checkbox = screen.getByRole("checkbox", { name: "Entlassungsbrief bereithalten" });
    checkbox.focus();
    await userEvent.keyboard(" ");
    await waitFor(() => expect(updateCaseStep).toHaveBeenCalledWith("step-document", "done"));
  });
});
