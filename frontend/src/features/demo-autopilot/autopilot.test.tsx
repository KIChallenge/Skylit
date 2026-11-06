import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Composer, type TypeRequest } from "@/features/chat";
import { typingDelay } from "@/features/chat/composer";

import { SCRIPTS, nextMessage, pickSamplerOption, scriptFor } from "./scripts";
import { useAutopilot, type AutopilotInput } from "./use-autopilot";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.sessionStorage.clear();
});

describe("demo scripts", () => {
  it("uses the selected script only for its persona", () => {
    expect(scriptFor("vorsorge", "stefan")?.id).toBe("vorsorge");
    expect(scriptFor("vorsorge", "maria")?.id).toBe("pflegegeld");
    expect(scriptFor(null, "elif")?.id).toBe("englisch");
    expect(scriptFor(null, "unknown")).toBeNull();
  });

  it("finds the first message not sent yet, also after hand-typed steps", () => {
    const script = SCRIPTS.vorsorge;
    expect(nextMessage(script, [])?.text).toBe(script.messages[0].text);
    expect(nextMessage(script, [`${script.messages[0].text} `, "Eine freie Frage"])?.text).toBe(script.messages[1].text);
    expect(nextMessage(script, script.messages.map((message) => message.text))).toBeNull();
  });

  it("picks SAMPLER options like record_demo.py", () => {
    const keywords = SCRIPTS.kopfschmerz.sampler?.S_O;
    expect(pickSamplerOption(["Seit heute", "Vor 2–3 Tagen", "Länger"], keywords)).toBe("Vor 2–3 Tagen");
    expect(pickSamplerOption(["Plötzlich und stark", "Weiß nicht", "Langsam"])).toBe("Weiß nicht");
    expect(pickSamplerOption(["Plötzlich", "Langsam"])).toBe("Langsam");
  });
});

describe("Composer typing", () => {
  // Fixed randomness keeps the typing pace deterministic.
  beforeEach(() => { vi.spyOn(Math, "random").mockReturnValue(0.5); });
  afterEach(() => { vi.restoreAllMocks(); });

  it("types the request, finishes with Enter and sends only on the next Enter", () => {
    vi.useFakeTimers();
    const onSend = vi.fn();
    const request: TypeRequest = { id: 1, text: "Hallo Lotse." };
    render(<Composer sending={false} onSend={onSend} typeRequest={request} />);
    const input = screen.getByRole("textbox");
    act(() => { vi.advanceTimersByTime(400); });
    const partial = (input as HTMLTextAreaElement).value;
    expect(partial.length).toBeGreaterThan(0);
    expect(partial.length).toBeLessThan(request.text.length);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(input).toHaveValue("Hallo Lotse.");
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSend).toHaveBeenCalledExactlyOnceWith("Hallo Lotse.");
  });

  it("stops typing on a real keystroke and keeps the text", () => {
    vi.useFakeTimers();
    render(<Composer sending={false} onSend={vi.fn()} typeRequest={{ id: 1, text: "Eine lange Nachricht" }} />);
    const input = screen.getByRole("textbox");
    act(() => { vi.advanceTimersByTime(400); });
    const kept = (input as HTMLTextAreaElement).value;
    fireEvent.keyDown(input, { key: "x" });
    act(() => { vi.advanceTimersByTime(5000); });
    expect(input).toHaveValue(kept);
  });

  it("waits longer after punctuation and varies the pace per word", () => {
    expect(typingDelay(".", () => 0)).toBeGreaterThan(typingDelay("a", () => 1));
    expect(typingDelay("a", () => 0.5, 1.7)).toBeGreaterThan(typingDelay("a", () => 0.5, 0.5));
  });
});

function Probe(props: AutopilotInput) {
  const request = useAutopilot(props);
  return <output>{request?.text ?? ""}</output>;
}

describe("useAutopilot", () => {
  const base: AutopilotInput = { enabled: true, personaId: "stefan", sent: [], busy: false, openQuestion: null };
  const shortcut = (code: string) => fireEvent.keyDown(window, { code, ctrlKey: true, shiftKey: true });

  it("selects a script and requests its next message", () => {
    render(<Probe {...base} />);
    act(() => { shortcut("Digit4"); });
    act(() => { shortcut("Space"); });
    expect(screen.getByRole("status")).toHaveTextContent(SCRIPTS.vorsorge.messages[0].text);
  });

  it("does nothing while a turn streams or when it is off", () => {
    const { rerender } = render(<Probe {...base} busy />);
    act(() => { shortcut("Space"); });
    expect(screen.getByRole("status")).toHaveTextContent("");
    rerender(<Probe {...base} enabled={false} />);
    act(() => { shortcut("Space"); });
    expect(screen.getByRole("status")).toHaveTextContent("");
  });

  it("clicks the scripted SAMPLER option and focuses the send button", () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(<>
      <form>
        <input type="radio" name="o" value="Seit heute" onChange={onChange} />
        <input type="radio" name="o" value="Vor 2–3 Tagen" onChange={onChange} />
        <button type="submit">Antworten</button>
      </form>
      <Probe {...base} openQuestion={{ step: "S_O", options: ["Seit heute", "Vor 2–3 Tagen"] }} />
    </>);
    act(() => { shortcut("Space"); });
    act(() => { vi.advanceTimersByTime(500); });
    const picked = screen.getAllByRole("radio").find((radio) => (radio as HTMLInputElement).checked);
    expect(picked).toHaveAttribute("value", "Vor 2–3 Tagen");
    expect(screen.getByRole("button", { name: "Antworten" })).toHaveFocus();
  });
});
