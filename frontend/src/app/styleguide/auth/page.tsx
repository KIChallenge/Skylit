import type { Metadata } from "next";
import { AuthPreview } from "./auth-preview";

export const metadata: Metadata = {
  title: "Demo-Personas · SV KI-Lotse",
  robots: { index: false },
};

export default function AuthPreviewPage() {
  return <AuthPreview />;
}
