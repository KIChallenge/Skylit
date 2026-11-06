import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { mailtoHref } from "./email-draft-card";
import { ResultCard } from "./result-cards";

const card = {
  type: "email_draft",
  email: {
    to_label: "Demo-Ordination Dr. Nora Wolkenfeld",
    to_email: null,
    subject: "Kopfschmerzen seit gestern",
    body: "Sehr geehrte Frau Dr. Wolkenfeld,\n\nBeginn: seit gestern.",
  },
};

beforeEach(() => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("e-mail draft card", () => {
  it("shows an editable draft that the person sends from the own mail program", () => {
    render(<ResultCard card={card} />);
    expect(screen.getByRole("heading", { name: "E-Mail-Entwurf" })).toBeInTheDocument();
    expect(screen.getByText("Demo-Ordination Dr. Nora Wolkenfeld")).toBeInTheDocument();
    expect(screen.getByText("Von Ihnen zu prüfen")).toBeInTheDocument();
    expect(screen.getByLabelText("E-Mail-Adresse")).toHaveValue("");
    expect(screen.getByText(/Der Lotse kennt sie nicht/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), { target: { value: "ordination@beispiel.example" } });
    fireEvent.change(screen.getByLabelText("Betreff"), { target: { value: "Termin" } });
    const link = screen.getByRole("link", { name: "In E-Mail-Programm öffnen" });
    expect(link).toHaveAttribute("href", expect.stringMatching(/^mailto:ordination@beispiel\.example\?subject=Termin&body=Sehr%20geehrte/));
    expect(screen.getByRole("button", { name: "Text kopieren" })).toBeInTheDocument();
  });

  it("marks an invalid address and keeps it out of the link", () => {
    render(<ResultCard card={card} />);
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), { target: { value: "keine adresse" } });
    expect(screen.getByLabelText("E-Mail-Adresse")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Bitte prüfen Sie die E-Mail-Adresse.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "In E-Mail-Programm öffnen" })).toHaveAttribute("href", expect.stringMatching(/^mailto:\?subject=/));
  });

  it("encodes line breaks and umlauts in the mailto link", () => {
    expect(mailtoHref("", "Übelkeit", "a\nb")).toBe("mailto:?subject=%C3%9Cbelkeit&body=a%0Ab");
  });
});
