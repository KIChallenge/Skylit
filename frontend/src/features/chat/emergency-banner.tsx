import { Phone, Siren } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Contact } from "@/lib/api";

export type EmergencyBannerProps = {
  contacts: Contact[];
  message: string;
};

/** Always visible. The parent places this in AppShell.emergencyBanner. */
export function EmergencyBanner({ contacts, message }: EmergencyBannerProps) {
  return (
    <section role="alert" className="rounded-xl bg-emergency-solid px-4 py-6 text-on-emergency shadow-overlay sm:px-6">
      <div className="mx-auto flex max-w-content items-start gap-4">
        <Siren aria-hidden className="size-8 shrink-0" strokeWidth={2} />
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <p className="text-label">Notfall</p>
          <h2 className="text-title font-bold">Bitte holen Sie sofort Hilfe</h2>
          <p className="max-w-answer whitespace-pre-wrap text-body wrap-anywhere">{message}</p>
          {contacts.length ? (
            <ul className="flex flex-col gap-4 sm:flex-row sm:flex-wrap" aria-label="Notfallkontakte">
              {contacts.map((contact, index) => (
                <li key={`${contact.name}-${index}`} className="flex min-w-0 flex-col gap-1">
                  {contact.phone ? (
                    <Button asChild variant="emergency" size="lg" className="h-auto min-h-12 w-full whitespace-normal border border-current py-3 focus-visible:outline-on-emergency focus-visible:ring-on-emergency focus-visible:ring-offset-emergency-solid sm:w-auto">
                      <a href={`tel:${contact.phone.replace(/[\s().-]/g, "")}`}>
                        <Phone aria-hidden />
                        <span className="min-w-0 wrap-anywhere"><bdi>{contact.phone}</bdi> anrufen – {contact.name}</span>
                      </a>
                    </Button>
                  ) : <p className="text-label">{contact.name}</p>}
                  {contact.hours ? <p className="text-caption">{contact.hours}</p> : null}
                  {contact.note ? <p className="text-body wrap-anywhere">{contact.note}</p> : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}
