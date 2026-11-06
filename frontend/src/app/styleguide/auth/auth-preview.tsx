"use client";

import { useEffect, useRef, useState } from "react";
import { AppHeader } from "@/components/layout/app-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { PersonaLogin, PersonaMenu } from "@/features/auth";
import { demoClient } from "@/features/auth/demo-client";
import type { Me } from "@/lib/api";

export function AuthPreview() {
  const [me, setMe] = useState<Me | null>(null);
  const content = useRef<HTMLElement>(null);
  const previousMe = useRef(me);

  useEffect(() => {
    if (previousMe.current !== me) {
      content.current?.focus();
      previousMe.current = me;
    }
  }, [me]);

  return (
    <div className="min-h-dvh bg-page">
      <a href="#auth-preview" className="sr-only focus:not-sr-only focus:block focus:p-4">Zum Inhalt</a>
      <header className="border-b bg-surface px-4 py-4 sm:px-8">
        <AppHeader actions={me ? <PersonaMenu me={me} client={demoClient} onLoggedOut={() => setMe(null)} /> : undefined} />
      </header>
      <main ref={content} id="auth-preview" tabIndex={-1} className="mx-auto max-w-content px-4 py-10 outline-offset-4 sm:px-8 sm:py-16">
        {me ? (
          <Card>
            <CardHeader className="gap-4">
              <Badge variant="outline" className="self-start">Synthetische Demo-Persona</Badge>
              <h1 className="text-title">Angemeldet als {me.display_name}</h1>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-body text-text-secondary">Das Persona-Menü in der Kopfzeile enthält die Abmeldung.</p>
              <p role="status" className="text-body">Die Anmeldung war erfolgreich. Diese Vorschau startet kein Gespräch.</p>
            </CardContent>
          </Card>
        ) : <PersonaLogin client={demoClient} onAuthenticated={setMe} />}
      </main>
    </div>
  );
}
