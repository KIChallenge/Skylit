import type { Metadata } from "next";
import { TransparencyPreview } from "./transparency-preview";

export const metadata: Metadata = {
  title: "Antwort und Transparenz – SV KI-Lotse",
  robots: { index: false },
};

export default function TransparencyPage() {
  return <TransparencyPreview />;
}
