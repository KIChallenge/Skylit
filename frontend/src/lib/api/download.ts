import { api } from "./client";
import { config } from "@/lib/config";

export type DownloadOptions = {
  filename: string;
  /** Open the verified original in a new tab instead of downloading it. */
  open?: boolean;
  timeoutMs?: number;
  /** Allowed media types for a download. Default: PDF only. */
  accept?: readonly string[];
};

/** Fetch once with cookie auth. Never navigate to a backend error response. */
export async function downloadFile(url: string, options: DownloadOptions): Promise<void> {
  let preview: Window | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const controller = new AbortController();
  try {
    const resolved = api.resolveUrl(url);
    const parsed = new URL(resolved, window.location.href);
    if (!["http:", "https:"].includes(parsed.protocol)) throw new Error();
    if (options.open) {
      preview = window.open("about:blank", "_blank");
      if (!preview) throw new Error();
      preview.opener = null;
    }
    timer = setTimeout(() => controller.abort(), options.timeoutMs ?? config.apiTimeoutMs);
    const response = await fetch(resolved, {
      credentials: config.apiCredentials,
      signal: controller.signal,
    });
    if (!response.ok) throw new Error();
    const mime = response.headers.get("content-type")?.split(";")[0].trim().toLowerCase();
    const allowed = options.open
      ? ["application/pdf", "image/png", "image/jpeg", "image/webp"]
      : options.accept ?? ["application/pdf"];
    if (!mime || !allowed.includes(mime)) throw new Error();
    const blob = await response.blob();
    if (!blob.size || controller.signal.aborted) throw new Error();
    const objectUrl = URL.createObjectURL(blob);
    if (preview) {
      preview.location.href = objectUrl;
    } else {
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = options.filename;
      document.body.append(link);
      link.click();
      link.remove();
    }
    // Keep the URL alive until the browser has consumed the download or preview.
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  } catch {
    preview?.close();
    throw new Error(controller.signal.aborted
      ? "Das Laden dauert zu lange. Bitte versuchen Sie es erneut."
      : "Die Datei konnte nicht geladen werden. Bitte versuchen Sie es erneut.");
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}
