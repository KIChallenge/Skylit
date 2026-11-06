"use client";

import { LocateFixed, MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

import { rememberLocationChoice, shouldOfferLocation, useLocation } from "./location-context";

/**
 * Explains location sharing once, then opens the browser's own permission prompt.
 * The browser prompt alone does not say why the Lotse needs the location.
 */
export function LocationDialog() {
  const location = useLocation();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let active = true;
    void shouldOfferLocation().then((offer) => { if (active && offer) setOpen(true); });
    return () => { active = false; };
  }, []);

  if (!location) return null;

  function dismiss() {
    rememberLocationChoice("dismissed");
    setOpen(false);
  }

  async function allow() {
    setOpen(false);
    const coords = await location!.request();
    if (coords) toast("Standort freigegeben. Entfernungen gelten jetzt ab Ihrem Standort.");
    else toast("Standort nicht verfügbar. Der Lotse rechnet ab Ihrer Postleitzahl.");
  }

  return <Dialog open={open} onOpenChange={(next) => { if (!next) dismiss(); }}>
    <DialogContent>
      <DialogHeader>
        <span className="flex size-12 items-center justify-center rounded-full bg-accent-subtle text-accent-text">
          <MapPin aria-hidden className="size-6" strokeWidth={1.5} />
        </span>
        <DialogTitle>Standort für genauere Entfernungen?</DialogTitle>
        <DialogDescription>
          Mit Ihrem Standort misst der Lotse die Entfernung zu Ordinationen genauer als mit der Postleitzahl.
        </DialogDescription>
      </DialogHeader>
      <ul className="list-disc space-y-1 ps-5 text-body text-text-secondary">
        <li>Ihr Browser fragt Sie gleich selbst um Erlaubnis.</li>
        <li>Der Standort geht nicht an das KI-Modell und wird nicht gespeichert.</li>
        <li>Ohne Standort rechnet der Lotse ab Ihrer Postleitzahl.</li>
      </ul>
      <DialogFooter>
        <Button variant="ghost" onClick={dismiss}>Nicht jetzt</Button>
        <Button onClick={() => void allow()}><LocateFixed />Standort freigeben</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}
