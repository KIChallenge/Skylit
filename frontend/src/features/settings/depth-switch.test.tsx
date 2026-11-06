import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const toastError = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({ toast: { error: toastError } }));

import type { Me } from "@/lib/api";

import { DepthSwitch } from "./depth-switch";

const me = (depth: Me["profile"]["depth"]): Me => ({
  user_id: "u1", persona_id: "maria", display_name: "Maria Berger",
  profile: { language: "de", depth, bundesland: "Wien", postal_code: "1030", insurer: "OEGK", date_of_birth: null },
});

afterEach(() => { cleanup(); toastError.mockReset(); });

describe("answer length switch", () => {
  it("shows the saved setting and saves a new one", async () => {
    const updateProfile = vi.fn(async () => me("detailed"));
    render(<DepthSwitch initial="short" client={{ updateProfile }} />);
    expect(screen.getByRole("group", { name: "Antwortlänge" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Kurz/ })).toBeChecked();

    fireEvent.click(screen.getByRole("radio", { name: /Ausführlich/ }));

    expect(screen.getByRole("radio", { name: /Ausführlich/ })).toBeChecked();
    await waitFor(() => expect(updateProfile).toHaveBeenCalledWith({ depth: "detailed" }));
    expect(screen.getByRole("radio", { name: /Ausführlich/ })).toBeChecked();
    expect(toastError).not.toHaveBeenCalled();
  });

  it("reverts and tells the person when saving fails", async () => {
    const updateProfile = vi.fn(async () => { throw new Error("offline"); });
    render(<DepthSwitch initial="short" client={{ updateProfile }} />);

    fireEvent.click(screen.getByRole("radio", { name: /Ausführlich/ }));

    await waitFor(() => expect(screen.getByRole("radio", { name: /Kurz/ })).toBeChecked());
    expect(toastError).toHaveBeenCalledWith("Die Einstellung wurde nicht gespeichert.", expect.anything());
  });

  it("does not save when the current setting is chosen again", () => {
    const updateProfile = vi.fn(async () => me("short"));
    render(<DepthSwitch initial="short" client={{ updateProfile }} />);
    fireEvent.click(screen.getByRole("radio", { name: /Kurz/ }));
    expect(updateProfile).not.toHaveBeenCalled();
  });
});
