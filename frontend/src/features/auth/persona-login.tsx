"use client";

import { ArrowRight, Bot, FlaskConical, UsersRound } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Enter } from "@/components/ui/enter";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { api, type ApiClient, type Me, type Persona } from "@/lib/api";

export type PersonaLoginProps = {
  onAuthenticated: (me: Me) => void;
  client?: ApiClient;
};

export function PersonaLogin({ onAuthenticated, client = api }: PersonaLoginProps) {
  const headingId = useId();
  const [result, setResult] = useState<{
    client: ApiClient;
    attempt: number;
    personas: Persona[];
    failed: boolean;
  } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const loading = result?.client !== client || result?.attempt !== attempt;
  const personas = loading ? [] : result?.personas ?? [];
  const loadError = !loading && result?.failed;
  const [pending, setPending] = useState<string | null>(null);
  const [failed, setFailed] = useState<Persona | null>(null);
  const busy = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    void client.listPersonas({ signal: controller.signal }).then(
      (personas) => { if (active) setResult({ client, attempt, personas, failed: false }); },
      () => { if (active) setResult({ client, attempt, personas: [], failed: true }); },
    );
    return () => { active = false; controller.abort(); };
  }, [client, attempt]);

  async function login(persona: Persona) {
    if (busy.current) return;
    busy.current = true;
    setPending(persona.id);
    setFailed(null);
    let me: Me;
    try {
      me = await client.login(persona.id);
    } catch {
      if (mounted.current) { setPending(null); setFailed(persona); }
      busy.current = false;
      return;
    }
    busy.current = false;
    if (mounted.current) { setPending(null); onAuthenticated(me); }
  }

  return (
    <section aria-labelledby={headingId} className="mx-auto flex w-full max-w-content flex-col gap-10">
      <Enter className="flex flex-col items-center gap-5 text-center">
        <Badge variant="outline" className="glass"><FlaskConical aria-hidden />Synthetische Demo-Personas</Badge>
        <h1 id={headingId} className="max-w-3xl text-display tracking-tight text-balance">Aus Ihrer Lage wird ein nächster Schritt.</h1>
        <p className="max-w-answer text-answer text-pretty text-text-secondary">
          Der SV KI-Lotse hilft Ihnen, Leistungen, Formulare und zuständige Stellen zu finden.
        </p>
        <p className="text-body text-text-secondary">Wählen Sie eine Demo-Persona. Alle Personen und ihre Angaben sind erfunden.</p>
      </Enter>

      <p role="status" className="text-center text-label text-text-secondary">
        {loading ? "Demo-Personas werden geladen…" : pending ? "Anmeldung läuft…" : ""}
      </p>
      {loading ? (
        <div aria-hidden className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((key) => <Card key={key} className="gap-4 p-6"><Skeleton className="size-12 rounded-full" /><Skeleton className="h-6 w-3/4" /><Skeleton className="h-16 w-full" /></Card>)}
        </div>
      ) : loadError ? (
        <ErrorState title="Die Demo-Personas konnten nicht geladen werden." onRetry={() => setAttempt((value) => value + 1)} />
      ) : personas.length === 0 ? (
        <EmptyState icon={UsersRound} title="Keine Demo-Personas verfügbar." description="Laden Sie die Auswahl erneut."
          action={<Button variant="secondary" onClick={() => setAttempt((value) => value + 1)}>Erneut versuchen</Button>} />
      ) : (
        <div className="grid items-stretch gap-4 md:grid-cols-3">
          {personas.map((persona, index) => (
            <Enter key={persona.id} index={index} className="min-w-0">
              <Card className="h-full gap-0 py-0 transition-[box-shadow,transform] duration-150 ease-out hover:-translate-y-0.5 hover:shadow-overlay motion-reduce:hover:translate-y-0">
                <Button type="button" variant="ghost" disabled={pending !== null} onClick={() => void login(persona)}
                  aria-label={`Als ${persona.display_name} anmelden`} aria-busy={pending === persona.id}
                  className="h-auto flex-1 flex-col items-start justify-start gap-6 rounded-xl p-7 text-start whitespace-normal hover:bg-transparent">
                  <span className="flex w-full flex-wrap items-center justify-between gap-3">
                    <Avatar size="lg" aria-hidden><AvatarFallback className="bg-accent-subtle text-accent-text">{persona.display_name.split(" ").map((part) => part[0]).join("")}</AvatarFallback></Avatar>
                    <Badge variant="neutral">Demo-Persona</Badge>
                  </span>
                  <span className="flex flex-col gap-2">
                    <span className="text-heading break-words">{persona.display_name}</span>
                    <span className="text-body font-normal text-pretty text-text-secondary">{persona.tagline}</span>
                  </span>
                  <span className="mt-auto flex items-center gap-2 pt-2 text-label text-accent-text">
                    {pending === persona.id ? "Anmeldung läuft…" : "Mit dieser Persona starten"}<ArrowRight aria-hidden />
                  </span>
                </Button>
                {failed?.id === persona.id ? (
                  <div className="p-4 pt-0"><ErrorState title="Die Anmeldung ist fehlgeschlagen." description="Bitte melden Sie diese Demo-Persona erneut an." onRetry={() => void login(persona)} /></div>
                ) : null}
              </Card>
            </Enter>
          ))}
        </div>
      )}
      <div className="glass mx-auto flex max-w-3xl items-start gap-3 rounded-xl p-5">
        <Bot aria-hidden className="mt-0.5 size-5 shrink-0 text-text-secondary" strokeWidth={1.5} />
        <p className="max-w-answer text-body text-pretty text-text-secondary">
          Sie nutzen einen KI-Assistenten. Antworten können Fehler enthalten. Der Lotse gibt keine medizinische Beratung.
          Die zuständige Stelle entscheidet über Leistungen.
        </p>
      </div>
    </section>
  );
}
