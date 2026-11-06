import type { Metadata } from "next";

import { CasePreview } from "./preview";

export const metadata: Metadata = { title: "Mein Fall – Vorschau", robots: { index: false } };

export default function CasePreviewPage() {
  return <CasePreview />;
}
