import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { downloadFile } from "./download";

beforeEach(() => { vi.stubEnv("NEXT_PUBLIC_API_URL", "https://backend.example"); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("safe downloads", () => {
  it("downloads a verified PDF with credentials and a resolved relative URL", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn().mockResolvedValue(new Response("%PDF-1.4 demo", { headers: { "content-type": "application/pdf" } }));
    vi.stubGlobal("fetch", fetch);
    const create = vi.fn().mockReturnValue("blob:verified");
    const revoke = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: create });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await downloadFile("/api/forms/draft/pdf", { filename: "pflegegeld.pdf" });
    expect(fetch).toHaveBeenCalledWith("https://backend.example/api/forms/draft/pdf", expect.objectContaining({ credentials: "include", signal: expect.any(AbortSignal) }));
    expect(click).toHaveBeenCalledOnce();
    expect(create).toHaveBeenCalledOnce();
    expect(document.querySelector("a[download]")).toBeNull();
    vi.advanceTimersByTime(60_000);
    expect(revoke).toHaveBeenCalledWith("blob:verified");
  });

  it.each([
    [200, "application/json", '{"detail":"private"}'],
    [200, "text/html", "<html>stacktrace</html>"],
    [500, "application/pdf", "error"],
    [200, "application/pdf", ""],
  ])("rejects unsafe responses (%s, %s) without navigating", async (status, mime, body) => {
    const fetch = vi.fn().mockResolvedValue(new Response(body, { status, headers: { "content-type": mime } }));
    vi.stubGlobal("fetch", fetch);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await expect(downloadFile("/api/forms/draft/pdf", { filename: "draft.pdf" })).rejects.toThrow("Die Datei konnte nicht geladen werden.");
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(click).not.toHaveBeenCalled();
  });

  it("aborts on timeout without repeating the request", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn((_url, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new Error("aborted")));
    }));
    vi.stubGlobal("fetch", fetch);
    const result = expect(downloadFile("/api/forms/slow/pdf", { filename: "draft.pdf", timeoutMs: 50 })).rejects.toThrow("Das Laden dauert zu lange.");
    await vi.advanceTimersByTimeAsync(51);
    await result;
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("closes the original preview when the backend returns an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("private", { status: 404 })));
    const preview = { opener: window, location: { href: "about:blank" }, close: vi.fn() };
    vi.spyOn(window, "open").mockReturnValue(preview as unknown as Window);
    await expect(downloadFile("/api/documents/missing/file", { filename: "original", open: true })).rejects.toThrow("Die Datei konnte nicht geladen werden.");
    expect(preview.close).toHaveBeenCalledOnce();
    expect(preview.location.href).toBe("about:blank");
    expect(preview.opener).toBeNull();
  });

  it("rejects script URLs before fetching", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(downloadFile("javascript:alert(1)", { filename: "draft.pdf" })).rejects.toThrow("Die Datei konnte nicht geladen werden.");
    expect(fetch).not.toHaveBeenCalled();
  });
});
