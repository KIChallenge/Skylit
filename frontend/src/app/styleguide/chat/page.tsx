import type { Metadata } from "next";

import { ChatPreview } from "./preview";

export const metadata: Metadata = { title: "Gespräch · Vorschau", robots: { index: false } };

export default function ChatStyleguidePage() {
  return <ChatPreview />;
}
