"use client";

import { Menu, Route } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

export type AppShellProps = {
  /** Kopfbereich: usually <AppHeader />. */
  header: ReactNode;
  /** Gesprächsliste. Column from 1440 px, sheet below. */
  navigation?: ReactNode;
  /** Gespräch. Always visible, scrolls on its own. */
  conversation: ReactNode;
  /** „Mein Fall". Column from 1024 px, sheet below. */
  casePanel?: ReactNode;
  /** Notfall-Banner. Full width under the header, before <main> in the DOM. */
  emergencyBanner?: ReactNode;
  /** „Kalender". Bottom of the „Mein Fall" column; it marks itself `data-calendar="expanded"` to fill the column. */
  calendar?: ReactNode;
  /** Label of the mobile „Mein Fall" button, e.g. „Mein Fall · 3 offen". */
  casePanelLabel?: string;
  className?: string;
};

/** „Mein Fall" gives the column to a maximized calendar. */
const hideWhenCalendarExpanded = "group-has-[[data-calendar=expanded]]/side:hidden";

/**
 * Three-column layout of the Lotse screen (DESIGN.md §5).
 * Pure layout: no API calls, no auth, no feature imports. Slots take ReactNode.
 * Each column scrolls on its own inside 100dvh.
 */
export function AppShell({
  header,
  navigation,
  conversation,
  casePanel,
  calendar,
  emergencyBanner,
  casePanelLabel = "Mein Fall",
  className,
}: AppShellProps) {
  const [navOpen, setNavOpen] = useState(false);
  const [caseOpen, setCaseOpen] = useState(false);
  const conversationId = useId();

  return (
    <div className={cn("flex h-dvh flex-col", className)}>
      <a
        href={`#${conversationId}`}
        className="sr-only z-50 rounded-md bg-surface p-3 text-label text-accent-text focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
      >
        Zum Gespräch
      </a>
      <header className="flex min-h-(--header-height) shrink-0 flex-wrap items-center gap-2 px-4 py-2 sm:h-(--header-height) sm:flex-nowrap sm:px-6 sm:py-0">
        {navigation ? (
          <Sheet open={navOpen} onOpenChange={setNavOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="laptop:hidden" aria-label="Gespräche anzeigen">
                <Menu />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-nav max-w-[85vw] gap-0 p-0">
              <SheetHeader className="border-b">
                <SheetTitle>Gespräche</SheetTitle>
                <SheetDescription className="sr-only">Ihre bisherigen Gespräche mit dem Lotsen</SheetDescription>
              </SheetHeader>
              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">{navigation}</div>
            </SheetContent>
          </Sheet>
        ) : null}
        <div className="flex min-w-0 flex-1 items-center">{header}</div>
        {casePanel ? (
          <Sheet open={caseOpen} onOpenChange={setCaseOpen}>
            <SheetTrigger asChild>
              <Button variant="secondary" size="sm" className="max-sm:w-full lg:hidden">
                <Route />
                <span className="tabular">{casePanelLabel}</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-md">
              <SheetHeader className="border-b">
                <SheetTitle>Mein Fall</SheetTitle>
                <SheetDescription className="sr-only">Ihre nächsten Schritte</SheetDescription>
              </SheetHeader>
              <div className="group/side flex min-h-0 flex-1 flex-col gap-3 pb-3">
                <div className={cn("min-h-0 flex-1 overflow-y-auto overscroll-contain", hideWhenCalendarExpanded)}>{casePanel}</div>
                {calendar ? <div className="contents [&>section]:mx-3">{calendar}</div> : null}
              </div>
            </SheetContent>
          </Sheet>
        ) : null}
      </header>

      {emergencyBanner ? <div className="shrink-0 px-3 pb-3 sm:px-4">{emergencyBanner}</div> : null}

      <div className="flex min-h-0 flex-1 gap-3 px-3 pb-3 sm:gap-4 sm:px-4 sm:pb-4">
        {navigation ? (
          <nav
            aria-label="Gespräche"
            className="glass hidden w-nav shrink-0 overflow-y-auto overscroll-contain rounded-xl shadow-card laptop:block beamer:w-nav-beamer"
          >
            {navigation}
          </nav>
        ) : null}

        <main id={conversationId} tabIndex={-1} className="relative flex min-w-0 flex-1 flex-col">
          {conversation}
        </main>

        {casePanel ? (
          <div className="group/side hidden w-case shrink-0 flex-col gap-3 sm:gap-4 lg:flex laptop:w-case-laptop beamer:w-case-beamer">
            <aside
              aria-label="Mein Fall"
              className={cn("glass min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-xl shadow-card", hideWhenCalendarExpanded)}
            >
              {casePanel}
            </aside>
            {calendar}
          </div>
        ) : null}
      </div>
    </div>
  );
}
