import type { Metadata } from "next";

import { UploadPreview } from "./upload-preview";

export const metadata: Metadata = {
  title: "Dokument anhängen – Vorschau",
  robots: { index: false },
};

export default function UploadPage() {
  return <UploadPreview />;
}
