import type { ApiClient, Me, Persona } from "@/lib/api";

/** Synthetic seed personas. Only the styleguide and feature tests use this client. */
export const demoPersonas: Persona[] = [
  { id: "maria", display_name: "Maria Berger", tagline: "Pflegt ihre Mutter nach dem Spitalsaufenthalt", avatar_emoji: "👩" },
  { id: "stefan", display_name: "Stefan Gruber", tagline: "Selbstständig, will gesünder leben", avatar_emoji: "🧑" },
  { id: "elif", display_name: "Elif Yılmaz", tagline: "Mutter eines 2-jährigen Kindes", avatar_emoji: "👩‍👧" },
];

const retrieved = "2026-11-06T08:00:00Z";
const profiles: Record<string, Me["profile"]> = {
  maria: { language: "de", depth: "short", bundesland: "Wien", postal_code: "1030", insurer: "OEGK", date_of_birth: "1974-06-02", first_name: "Maria", last_name: "Berger", svnr: "1234020674", insurance_status: "Pflichtversichert (Angestellte)", street: "Demogasse 7", city: "Wien", co_insured: [], sv_retrieved_at: retrieved },
  stefan: { language: "de", depth: "detailed", bundesland: "Wien", postal_code: "1100", insurer: "SVS", date_of_birth: "1988-01-20", first_name: "Stefan", last_name: "Gruber", svnr: "4564200188", insurance_status: "Selbstständig (SVS)", street: "Beispielgasse 15", city: "Wien", co_insured: [], sv_retrieved_at: retrieved },
  elif: { language: "en", depth: "short", bundesland: "Wien", postal_code: "1160", insurer: "OEGK", date_of_birth: "1995-09-11", first_name: "Elif", last_name: "Yılmaz", svnr: "7898110995", insurance_status: "Pflichtversichert (Angestellte)", street: "Mustergasse 3", city: "Wien", co_insured: [{ first_name: "Deniz", last_name: "Yılmaz", date_of_birth: "2024-03-18", relation: "Kind" }], sv_retrieved_at: retrieved },
};

export function demoMe(personaId: string): Me {
  const persona = demoPersonas.find((item) => item.id === personaId);
  if (!persona) throw new Error("Unknown demo persona");
  return { user_id: `00000000-0000-4000-8000-${String(demoPersonas.indexOf(persona) + 1).padStart(12, "0")}`, persona_id: persona.id, display_name: persona.display_name, profile: profiles[persona.id] };
}

/** No network: reject any call outside the persona preview flow. */
async function unsupported(): Promise<never> { throw new Error("Unsupported demo request"); }

export const demoClient: ApiClient = {
  listPersonas: async () => demoPersonas,
  login: async (personaId) => demoMe(personaId),
  logout: async () => {},
  getMe: unsupported,
  updateProfile: unsupported,
  listConversations: unsupported,
  createConversation: unsupported,
  getConversation: unsupported,
  getCase: unsupported,
  updateCaseStep: unsupported,
  uploadDocument: unsupported,
  getDocument: unsupported,
  getTransparency: unsupported,
  listCalendarEntries: unsupported,
  createCalendarEntry: unsupported,
  deleteCalendarEntry: unsupported,
  async *streamMessage() { throw new Error("Unsupported demo request"); },
  resolveUrl: () => { throw new Error("Unsupported demo request"); },
  documentFileUrl: () => { throw new Error("Unsupported demo request"); },
};
