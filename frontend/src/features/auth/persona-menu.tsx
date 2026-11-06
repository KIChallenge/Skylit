"use client";

import { ChevronDown, FlaskConical, LogOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ErrorState } from "@/components/ui/state";
import { api, type ApiClient, type Me } from "@/lib/api";

import { SvDataPanel } from "./sv-data-panel";

export type PersonaMenuProps = {
  me: Me;
  onLoggedOut: () => void;
  client?: ApiClient;
};

export function PersonaMenu({ me, onLoggedOut, client = api }: PersonaMenuProps) {
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const busy = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  async function logout() {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setFailed(false);
    try {
      await client.logout();
    } catch {
      if (mounted.current) { setPending(false); setFailed(true); setOpen(true); }
      busy.current = false;
      return;
    }
    busy.current = false;
    if (mounted.current) { setPending(false); setOpen(false); onLoggedOut(); }
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="secondary" aria-busy={pending} aria-label={`Persona-Menü: ${me.display_name}`} className="h-auto min-h-10 min-w-0 whitespace-normal py-2">
          <span className="break-words text-start">{me.display_name}</span><ChevronDown aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-case-laptop max-w-full">
        <DropdownMenuLabel className="flex flex-col gap-2">
          <span className="text-label break-words">{me.display_name}</span>
          <span className="flex items-center gap-2 text-caption text-text-secondary"><FlaskConical aria-hidden className="size-4" />Synthetische Demo-Persona</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {me.profile.svnr ? <><SvDataPanel profile={me.profile} /><DropdownMenuSeparator /></> : null}
        {failed ? <ErrorState className="m-2" title="Die Abmeldung ist fehlgeschlagen." description="Sie sind weiterhin angemeldet." /> : null}
        <DropdownMenuItem className="focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset" disabled={pending} onSelect={(event) => { event.preventDefault(); void logout(); }}>
          <LogOut aria-hidden />{pending ? "Abmeldung läuft…" : failed ? "Erneut versuchen" : "Abmelden"}
        </DropdownMenuItem>
        <p role="status" className="px-2 text-caption text-text-secondary">{pending ? "Abmeldung läuft…" : ""}</p>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
