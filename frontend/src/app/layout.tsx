import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { THEME_INIT_SCRIPT } from "@/components/layout/theme-toggle";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "SV KI-Lotse",
    template: "%s – SV KI-Lotse",
  },
  description:
    "Der SV KI-Lotse führt durch Leistungen, Formulare und zuständige Stellen der österreichischen Sozialversicherung.",
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: "#1a6444",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    // The init script sets data-theme before hydration; React must not warn about it.
    <html lang="de-AT" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
        <Toaster />
      </body>
    </html>
  );
}
