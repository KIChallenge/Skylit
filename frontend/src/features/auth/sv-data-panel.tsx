import { Database } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Me } from "@/lib/api";

type Profile = Me["profile"];

const INSURERS: Record<string, string> = { OEGK: "ÖGK", BVAEB: "BVAEB", SVS: "SVS" };
const TIME_ZONE = "Europe/Vienna";
const dateFormat = new Intl.DateTimeFormat("de-AT", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: TIME_ZONE });
const birthFormat = new Intl.DateTimeFormat("de-AT", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });

/** Show only the last 4 digits: "•••• ••0674". */
export function maskSvnr(svnr: string): string {
  return `•••• ••${svnr.slice(-4)}`;
}

function Row({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-text-secondary">{term}</dt>
      <dd className="min-w-0 break-words text-text">{children}</dd>
    </>
  );
}

/** Read-only result of the simulated SV data query (D-041). */
export function SvDataPanel({ profile }: { profile: Profile }) {
  if (!profile.svnr) return null;
  const name = [profile.first_name, profile.last_name].filter(Boolean).join(" ");
  const address = [profile.street, [profile.postal_code, profile.city].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  const coInsured = profile.co_insured ?? [];
  return (
    <section aria-labelledby="sv-data-title" className="flex flex-col gap-3 px-2 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="sv-data-title" className="text-label text-text">Meine Daten</h2>
        <Badge variant="outline"><Database aria-hidden />Demo-Daten</Badge>
      </div>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-caption">
        {name ? <Row term="Name">{name}</Row> : null}
        <Row term="SV-Nummer"><span aria-hidden className="tabular-nums">{maskSvnr(profile.svnr)}</span><span className="sr-only">endet auf {profile.svnr.slice(-4)}</span></Row>
        {profile.insurer ? <Row term="Versicherungsträger">{INSURERS[profile.insurer] ?? profile.insurer}</Row> : null}
        {profile.insurance_status ? <Row term="Versicherungsstatus">{profile.insurance_status}</Row> : null}
        {address ? <Row term="Adresse">{address}</Row> : null}
        <Row term="Mitversichert">
          {coInsured.length === 0 ? "keine Personen" : (
            <ul className="flex flex-col gap-0.5">
              {coInsured.map((person) => (
                <li key={`${person.first_name}-${person.date_of_birth}`}>
                  {person.first_name} {person.last_name} ({person.relation}, geb. {birthFormat.format(new Date(person.date_of_birth))})
                </li>
              ))}
            </ul>
          )}
        </Row>
      </dl>
      <p className="text-caption text-text-secondary">
        Quelle: simulierte SV-Datenabfrage
        {profile.sv_retrieved_at ? ` · Stand ${dateFormat.format(new Date(profile.sv_retrieved_at))}` : null}
      </p>
    </section>
  );
}
