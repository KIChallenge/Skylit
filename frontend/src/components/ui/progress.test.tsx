import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Progress } from "@/components/ui/progress";

afterEach(cleanup);

describe("Progress accessibility", () => {
  it.each([0, 33, 100])("exposes the displayed value %i", (value) => {
    render(<Progress value={value} aria-label="Fortschritt" />);

    const progress = screen.getByRole("progressbar", { name: "Fortschritt" });
    expect(progress.getAttribute("aria-valuenow")).toBe(String(value));
    expect(progress.getAttribute("aria-valuemin")).toBe("0");
    expect(progress.getAttribute("aria-valuemax")).toBe("100");
    expect(progress.getAttribute("data-state")).toBe(value === 100 ? "complete" : "loading");
  });

  it("keeps an unknown value indeterminate", () => {
    render(<Progress aria-label="Fortschritt" />);

    const progress = screen.getByRole("progressbar", { name: "Fortschritt" });
    expect(progress.hasAttribute("aria-valuenow")).toBe(false);
    expect(progress.getAttribute("data-state")).toBe("indeterminate");
  });
});
