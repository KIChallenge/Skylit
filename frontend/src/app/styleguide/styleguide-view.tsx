"use client";

import {
  ChevronDown,
  Circle,
  CircleCheck,
  CircleDashed,
  CircleDot,
  ClipboardCheck,
  Download,
  FlaskConical,
  Handshake,
  LogOut,
  MessagesSquare,
  Paperclip,
  Plus,
  Route,
  Send,
  ShieldAlert,
  SignalHigh,
  SignalLow,
  SignalMedium,
  Siren,
  UserRound,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { AppHeader } from "@/components/layout/app-header";
import { AppShell } from "@/components/layout/app-shell";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Enter } from "@/components/ui/enter";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const colorGroups: { name: string; tokens: { token: string; className: string; note: string }[] }[] = [
  {
    name: "Neutral – Struktur",
    tokens: [
      { token: "--bg-page", className: "bg-page", note: "Seitengrund" },
      { token: "--bg-surface", className: "bg-surface", note: "deckende Flächen, Overlays" },
      { token: "--bg-glass", className: "glass", note: "Glas: Panels, Cards, Eingabe" },
      { token: "--bg-subtle", className: "bg-subtle", note: "getönte Flächen" },
      { token: "--bg-muted", className: "bg-muted", note: "Hover" },
      { token: "--border", className: "bg-border", note: "Kanten, Trenner" },
      { token: "--border-strong", className: "bg-border-strong", note: "Eingabe-Kanten · 3,9:1" },
      { token: "--text-secondary", className: "bg-text-secondary", note: "Sekundärtext · 7,4:1" },
      { token: "--text", className: "bg-text", note: "Text · 17:1" },
    ],
  },
  {
    name: "Tannengrün – sicherer Weg",
    tokens: [
      { token: "--accent-subtle", className: "bg-accent-subtle", note: "Sicherheit hoch, Erledigt" },
      { token: "--accent-border", className: "bg-accent-border", note: "Kante getönt" },
      { token: "--accent-text", className: "bg-accent-text", note: "Text, Links · 8,1:1" },
      { token: "--accent-solid", className: "bg-accent-solid", note: "Hauptaktion · Weiß 7,1:1" },
      { token: "--accent-solid-hover", className: "bg-accent-solid-hover", note: "Hover" },
    ],
  },
  {
    name: "Ocker – bitte prüfen",
    tokens: [
      { token: "--caution-subtle", className: "bg-caution-subtle", note: "Hinweisfläche" },
      { token: "--caution-border", className: "bg-caution-border", note: "Kante" },
      { token: "--caution-text", className: "bg-caution-text", note: "Text auf Fläche · 7,7:1" },
      { token: "--caution-solid", className: "bg-caution-solid", note: "Sicherheit niedrig · Weiß 7:1" },
    ],
  },
  {
    name: "Rot – nur Notfall",
    tokens: [
      { token: "--emergency-subtle", className: "bg-emergency-subtle", note: "kompakte Leiste" },
      { token: "--emergency-text", className: "bg-emergency-text", note: "Text · 7,2:1" },
      { token: "--emergency-solid", className: "bg-emergency-solid", note: "Banner · Weiß 6,6:1" },
    ],
  },
];

const typeScale = [
  { role: "display", className: "text-display", sample: "Aus Ihrer Lage wird ein Fall", spec: "2rem · 1.2 · 600" },
  { role: "title", className: "text-title", sample: "Pflege für Mutter organisieren", spec: "1.5rem · 1.25 · 600" },
  { role: "heading", className: "text-heading", sample: "Antrag auf Pflegegeld – Entwurf", spec: "1.125rem · 1.3 · 600" },
  {
    role: "answer",
    className: "text-answer",
    sample: "Pflegegeld könnte für Ihre Mutter in Frage kommen. Die PVA entscheidet über den Antrag.",
    spec: "1.125rem · 1.6 · 400",
  },
  { role: "body", className: "text-body", sample: "Meine Mutter wurde gestern aus dem Spital entlassen.", spec: "1rem · 1.5 · 400" },
  { role: "label", className: "text-label", sample: "PDF herunterladen", spec: "0.875rem · 1.4 · 600" },
  { role: "caption", className: "text-caption", sample: "5. November, 14:32 · eustella-v1.5", spec: "0.8125rem · 1.4 · 400" },
];

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <h2 id={id} className="text-title text-text">
        {title}
      </h2>
      {children}
    </section>
  );
}

function SampleNavigation() {
  const items = [
    { title: "Pflege für Mutter", date: "Heute, 14:32", open: 3, current: true },
    { title: "Reha nach Hüft-OP", date: "2. November", open: 1, current: false },
  ];
  return (
    <div className="flex flex-col gap-2 p-3">
      <Button variant="secondary" className="justify-start">
        <Plus />
        Neues Gespräch
      </Button>
      <ul className="flex flex-col gap-1">
        {items.map((item) => (
          <li key={item.title}>
            <a
              href="#"
              aria-current={item.current ? "page" : undefined}
              className="flex flex-col gap-0.5 rounded-md px-3 py-2 transition-[background-color] duration-150 hover:bg-muted aria-[current=page]:bg-accent-subtle"
            >
              <span className="text-label text-text">{item.title}</span>
              <span className="flex items-center gap-2 text-caption text-text-secondary">
                <span className="tabular">{item.date}</span>
                <Badge variant="neutral" className="tabular">
                  {item.open} offen
                </Badge>
              </span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SampleCasePanel() {
  const steps = [
    { title: "Entlassungsbrief hochladen", status: "Erledigt", Icon: CircleCheck, done: true },
    { title: "Pflegegeld bei der PVA beantragen", status: "In Arbeit", Icon: CircleDot, done: false },
    { title: "Hauskrankenpflege anfragen", status: "Offen", Icon: Circle, done: false },
  ];
  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-col gap-1">
        <p className="text-heading text-text">Pflege für Mutter organisieren</p>
        <p className="text-caption text-text-secondary">Für: Mutter (Anna Berger)</p>
      </div>
      <div className="flex flex-col gap-2">
        <p className="text-label text-text tabular">1 von 3 erledigt</p>
        <Progress value={33} aria-label="Fortschritt: 1 von 3 erledigt" />
      </div>
      <ol className="flex flex-col gap-3">
        {steps.map(({ title, status, Icon, done }) => (
          <li key={title} className="flex items-start gap-3">
            <Icon aria-hidden className={done ? "mt-0.5 size-5 text-accent-text" : "mt-0.5 size-5 text-text-secondary"} />
            <div className="flex flex-col">
              <span className="text-body text-text">{title}</span>
              <span className="text-caption text-text-secondary">{status}</span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function StyleguideView() {
  const [retries, setRetries] = useState(0);
  const [entered, setEntered] = useState(0);

  return (
    <div className="min-h-dvh bg-page">
      <header className="border-b bg-surface">
        <div className="mx-auto flex min-h-(--header-height) max-w-content items-center px-6 py-2">
          <AppHeader actions={<Badge variant="caution">Nur intern</Badge>} />
        </div>
      </header>

      <main className="mx-auto flex max-w-content flex-col gap-12 px-6 py-10">
        <div className="flex flex-col gap-2">
          <h1 className="text-display text-text">Styleguide</h1>
          <p className="max-w-answer text-answer text-pretty text-text-secondary">
            Richtung „Atmosphäre“: ruhig, weit und hell, mit Glasflächen über einem weichen Verlauf. Helles Design
            für den Beamer, dunkles Design per Umschalter. Tannengrün nur für Hauptaktion, hohe Sicherheit und
            erledigte Schritte. Rot nur für Notfälle.
          </p>
        </div>

        <Section id="farben" title="Farben">
          <div className="grid gap-6">
            {colorGroups.map((group) => (
              <div key={group.name} className="flex flex-col gap-3">
                <h3 className="text-heading text-text">{group.name}</h3>
                <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4">
                  {group.tokens.map((t) => (
                    <li key={t.token} className="flex flex-col gap-2 rounded-lg border bg-surface p-2">
                      <span className={`h-14 rounded-md border ${t.className}`} />
                      <span className="font-mono text-caption text-text">{t.token}</span>
                      <span className="text-caption text-text-secondary">{t.note}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Section>

        <Section id="schrift" title="Schrift">
          <p className="text-body text-text-secondary">Systemschrift, Gewichte 400 und 600. Ziffern mit tabular-nums.</p>
          <ul className="flex flex-col divide-y rounded-lg border bg-surface">
            {typeScale.map((t) => (
              <li key={t.role} className="grid gap-1 p-4 md:grid-cols-[10rem_1fr] md:items-baseline md:gap-6">
                <span className="font-mono text-caption text-text-secondary">
                  {t.role} · {t.spec}
                </span>
                <span className={`${t.className} max-w-answer text-text`}>{t.sample}</span>
              </li>
            ))}
          </ul>
          <p className="text-body text-text tabular">Tabellenziffern: 12 von 15 Feldern · 14:32 · 1.234,50 €</p>
        </Section>

        <Section id="buttons" title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button>
              <Send />
              Senden
            </Button>
            <Button variant="secondary">
              <Download />
              PDF herunterladen
            </Button>
            <Button variant="ghost">
              <Paperclip />
              Dokument anhängen
            </Button>
            <Button variant="link">Website öffnen</Button>
            <Button aria-disabled>Lotse antwortet…</Button>
            <Button disabled>Deaktiviert</Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Dokument anhängen">
                  <Paperclip />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Dokument anhängen</TooltipContent>
            </Tooltip>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="emergency" size="lg">
              <Siren />
              144 anrufen – Rettung
            </Button>
            <span className="text-caption text-text-secondary">Rot nur im Notfall-Banner. Mindesthöhe 48 px.</span>
          </div>
        </Section>

        <Section id="badges" title="Badges">
          <p className="text-body text-text-secondary">Jedes Badge hat Symbol und Text. Farbe ist nie das einzige Signal.</p>
          <div className="flex flex-wrap gap-2">
            <Badge variant="accent">
              <SignalHigh aria-hidden />
              Sicherheit: hoch
            </Badge>
            <Badge variant="caution">
              <SignalMedium aria-hidden />
              Sicherheit: mittel
            </Badge>
            <Badge variant="caution-strong">
              <SignalLow aria-hidden />
              Sicherheit: niedrig
            </Badge>
            <Badge variant="neutral">
              <CircleDashed aria-hidden />
              Sicherheit nicht verfügbar
            </Badge>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="caution">
              <ShieldAlert aria-hidden />
              Medizinische Frage – an Fachleute übergeben
            </Badge>
            <Badge variant="caution">
              <Handshake aria-hidden />
              An einen Menschen übergeben
            </Badge>
            <Badge variant="caution">
              <ClipboardCheck aria-hidden />
              Von Ihnen zu prüfen
            </Badge>
            <Badge variant="emergency">
              <Siren aria-hidden />
              Notfall
            </Badge>
            <Badge variant="outline">
              <FlaskConical aria-hidden />
              Demo-Daten
            </Badge>
            <Badge variant="accent">
              <CircleCheck aria-hidden />
              Erledigt
            </Badge>
          </div>
        </Section>

        <Section id="cards" title="Card und Formular">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-heading">Antrag auf Pflegegeld – Entwurf</CardTitle>
                <CardDescription>Pensionsversicherungsanstalt (PVA)</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Badge variant="caution">
                  <ClipboardCheck aria-hidden />
                  Von Ihnen zu prüfen
                </Badge>
                <p className="text-body text-pretty text-text">
                  Der Lotse hat den Antrag vorausgefüllt. Prüfen Sie jedes Feld. Sie unterschreiben und senden ihn
                  selbst.
                </p>
                <p className="text-caption text-text-secondary tabular">Ausgefüllt (12) · Fehlt noch (3)</p>
              </CardContent>
              <CardFooter>
                <Button variant="secondary">
                  <Download />
                  PDF herunterladen
                </Button>
              </CardFooter>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-heading">Eingabe</CardTitle>
                <CardDescription>Label, Textfeld und Checkbox</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="sg-message">Ihre Nachricht an den Lotsen</Label>
                  <Textarea id="sg-message" placeholder="Beschreiben Sie Ihre Lage…" rows={2} />
                </div>
                <div className="flex items-center gap-3">
                  <Checkbox id="sg-step" defaultChecked />
                  <Label htmlFor="sg-step" className="text-body font-normal">
                    Entlassungsbrief hochladen
                  </Label>
                </div>
              </CardContent>
            </Card>
          </div>
        </Section>

        <Section id="overlays" title="Sheet, Menü, Aufklappen, Toast">
          <div className="flex flex-wrap items-start gap-3">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="secondary">Warum diese Antwort?</Button>
              </SheetTrigger>
              <SheetContent side="right" className="sm:max-w-md">
                <SheetHeader>
                  <SheetTitle>Warum diese Antwort?</SheetTitle>
                  <SheetDescription>Quellen, Schritte des Lotsen und Modell zu dieser Antwort.</SheetDescription>
                </SheetHeader>
                <div className="flex flex-col gap-3 px-4">
                  <Badge variant="accent">
                    <SignalHigh aria-hidden />
                    Sicherheit: hoch
                  </Badge>
                  <p className="text-body text-text-secondary">
                    Die Stufe beschreibt die Beleglage dieser Antwort. Sie garantiert keine Richtigkeit.
                  </p>
                </div>
              </SheetContent>
            </Sheet>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost">
                  <Avatar className="size-7">
                    <AvatarFallback className="bg-accent-subtle text-caption text-accent-text">MB</AvatarFallback>
                  </Avatar>
                  Maria Berger
                  <ChevronDown />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuLabel>Demo-Persona</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>
                  <UserRound />
                  Persona wechseln
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <LogOut />
                  Abmelden
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Collapsible className="flex w-80 max-w-full flex-col gap-2 rounded-lg border bg-surface p-3">
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm" className="justify-between">
                  Alle 12 anzeigen
                  <ChevronDown />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="text-body text-text-secondary">
                Name: Anna Berger · Geburtsdatum: 14. März 1946 · Versicherungsträger: PVA
              </CollapsibleContent>
            </Collapsible>

            <Button variant="secondary" onClick={() => toast("Mein Fall: 3 neue Schritte.")}>
              Toast zeigen
            </Button>
            <Button
              variant="secondary"
              onClick={() => toast.error("Änderung nicht gespeichert. Erneut versuchen.")}
            >
              Fehler-Toast zeigen
            </Button>
          </div>
        </Section>

        <Section id="zustaende" title="Laden, leer, Fehler">
          <div className="grid gap-6 md:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-heading">Laden</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3" aria-busy="true" aria-label="Wird geladen">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-6 w-32 rounded-full" />
              </CardContent>
            </Card>
            <Card>
              <EmptyState
                icon={Route}
                title="Noch keine Schritte."
                description="Beschreiben Sie Ihre Lage. Der Lotse legt hier Ihre nächsten Schritte an."
              />
            </Card>
            <Card className="justify-center px-4">
              <ErrorState
                description={
                  retries > 0
                    ? `Bitte versuchen Sie es erneut. (${retries}. Versuch)`
                    : "Bitte versuchen Sie es erneut."
                }
                onRetry={() => setRetries((n) => n + 1)}
              />
            </Card>
          </div>
          <Card>
            <EmptyState icon={MessagesSquare} title="Noch keine Gespräche." />
          </Card>
        </Section>

        <Section id="bewegung" title="Bewegung">
          <p className="text-body text-text-secondary">
            Neue Inhalte: Opacity, 12 px, 4 px Blur, 300 ms ease-out, 100 ms gestaffelt. Bei reduzierter Bewegung nur
            Opacity.
          </p>
          <div>
            <Button variant="secondary" onClick={() => setEntered((n) => n + 1)}>
              Schritte erneut einblenden
            </Button>
          </div>
          <div key={entered} className="flex flex-col gap-2">
            {["Pflegegeld beantragen", "Hauskrankenpflege anfragen", "Beratung bei der PVA vereinbaren"].map(
              (title, i) => (
                <Enter key={title} index={i} className="rounded-lg border bg-surface p-3 text-body text-text shadow-card">
                  {title}
                </Enter>
              ),
            )}
          </div>
        </Section>

        <Section id="shell" title="App-Shell">
          <p className="text-body text-text-secondary">
            Gespräche ab 1440 px als Spalte, „Mein Fall“ ab 1024 px. Darunter öffnen Sheets.
          </p>
          <Separator />
          <div className="h-[36rem] overflow-hidden rounded-lg border shadow-card">
            <AppShell
              className="h-full"
              header={<AppHeader />}
              navigation={<SampleNavigation />}
              casePanel={<SampleCasePanel />}
              casePanelLabel="Mein Fall · 2 offen"
              conversation={
                <div className="flex flex-1 flex-col overflow-y-auto p-6">
                  <div className="mx-auto flex w-full max-w-answer flex-col gap-4">
                    <p className="self-end rounded-lg bg-accent-subtle px-4 py-2 text-body text-text">
                      Meine Mutter wurde gestern aus dem Spital entlassen und braucht jetzt Hilfe.
                    </p>
                    <p className="text-caption text-text-secondary">Lotse (KI)</p>
                    <p className="text-answer text-pretty text-text">
                      Das ist viel auf einmal. Pflegegeld könnte für Ihre Mutter in Frage kommen. Ich habe
                      Ihnen drei Schritte in „Mein Fall“ angelegt.
                    </p>
                  </div>
                </div>
              }
            />
          </div>
        </Section>
      </main>
    </div>
  );
}
