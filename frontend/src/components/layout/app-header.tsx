import { Bot, Compass } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { ThemeToggle } from "./theme-toggle";

/** Product wordmark: lucide Compass in fir green plus the product name. */
export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2 rounded-md text-heading text-text outline-offset-4"
      aria-label="SV KI-Lotse – Startseite"
    >
      <Compass aria-hidden className="size-6 text-accent-solid" strokeWidth={2} />
      <span className="whitespace-nowrap">SV KI-Lotse</span>
    </Link>
  );
}

/** Badge „KI-Assistent" with the Art. 50 hint as tooltip (DESIGN.md §11). */
export function AiAssistantBadge() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" className="rounded-full">
          <Badge variant="outline">
            <Bot aria-hidden />
            <span className="sm:hidden">KI</span>
            <span className="hidden sm:inline">KI-Assistent</span>
          </Badge>
        </button>
      </TooltipTrigger>
      <TooltipContent>Antworten können Fehler enthalten. Die zuständige Stelle entscheidet.</TooltipContent>
    </Tooltip>
  );
}

export type AppHeaderProps = {
  /** Right side, e.g. the persona menu. */
  actions?: ReactNode;
};

/** Content of the AppShell header slot. */
export function AppHeader({ actions }: AppHeaderProps) {
  return (
    <div className="flex w-full min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
      <Wordmark />
      <AiAssistantBadge />
      <div className="ml-auto flex items-center gap-2">
        <ThemeToggle />
        {actions}
      </div>
    </div>
  );
}
