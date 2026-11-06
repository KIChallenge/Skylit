/**
 * Demo scripts for the presenter autopilot (docs/PITCH.md, backend/scripts/record_demo.py).
 *
 * Replay hits only on the exact recorded text, so these strings must stay byte-identical to
 * `MESSAGES` and `CASES` in record_demo.py. Change both together and record again.
 */

export type ScriptId = "golden" | "englisch" | "kopfschmerz" | "pflegegeld" | "vorsorge";

export type ScriptMessage = {
  text: string;
  /** The presenter attaches the discharge letter before sending this message. */
  attach?: boolean;
};

export type DemoScript = {
  id: ScriptId;
  persona: string;
  messages: readonly ScriptMessage[];
  /** Keywords per SAMPLER step. The first option that contains one gets clicked. */
  sampler?: Readonly<Record<string, readonly string[]>>;
};

export const SCRIPTS: Readonly<Record<ScriptId, DemoScript>> = {
  golden: {
    id: "golden",
    persona: "maria",
    messages: [
      { text: "Meine Mutter ist gerade aus dem Spital gekommen und kommt allein nicht mehr zurecht. Was muss ich tun?" },
      { text: "Ja, sie wohnt in Wien. Hier ist der Brief.", attach: true },
      { text: "Bitte füll den Pflegegeldantrag für meine Mutter aus." },
      { text: "Soll meine Mutter das Ondansetron höher dosieren, ihr ist noch immer schlecht?" },
      { text: "Meine Mutter hat plötzlich starke Atemnot." },
    ],
  },
  englisch: {
    id: "englisch",
    persona: "elif",
    messages: [{ text: "Which check-ups does my 2-year-old need?" }],
  },
  kopfschmerz: {
    id: "kopfschmerz",
    persona: "stefan",
    messages: [
      { text: "Ich habe seit drei Tagen Kopfschmerzen und weiß nicht, wohin ich damit gehen soll." },
      { text: "Welche Hausärztinnen oder Hausärzte gibt es in 1100?" },
      { text: "Ja, bitte entwirf die E-Mail mit meinen Angaben an die Demo-Ordination Dr. Emil Kieselstern." },
    ],
    sampler: {
      S_O: ["2–3 tag", "2-3 tag", "mehrere tage", "schleichend", "allmählich"],
      S_P: ["bildschirm", "pause", "ruhe", "stress"],
      S_Q: ["drück", "druck", "dumpf"],
      S_R: ["stirn", "beidseit", "ganz"],
      S_S: ["4–5", "4–6", "4-6", "4-5", "mittel", "mäßig"],
      S_T: ["kommt und geht", "kommen und gehen", "nachmittag", "tagsüber"],
      A: ["keine"],
      M: ["keine"],
      P: ["keine", "nein"],
      L: ["weniger getrunken", "getrunken", "normal"],
      E: ["bildschirm", "stress"],
      R: ["bildschirm", "wenig bewegung", "sitz"],
    },
  },
  pflegegeld: {
    id: "pflegegeld",
    persona: "maria",
    messages: [
      {
        text: "Meine Mutter Anna ist gestern aus dem Spital entlassen worden. Sie wohnt allein in 1030 Wien. Hier ist der Entlassungsbrief. Welche Unterstützung bekommt sie?",
        attach: true,
      },
      { text: "Bitte füll den Pflegegeldantrag für meine Mutter aus." },
      { text: "Wo reiche ich den Antrag ein, und wer hilft uns bei der Pflege zu Hause?" },
      { text: "Bitte schlag mir einen Termin bei einer Pflegeberatung in 1030 vor." },
      {
        text: "Ich arbeite Vollzeit. Kann ich für die Pflege meiner Mutter in Pflegekarenz gehen? Bitte entwirf auch eine E-Mail an meinen Arbeitgeber an personal@arbeitgeber.example.",
      },
      { text: "Ja, bitte erstelle den E-Mail-Entwurf." },
    ],
  },
  vorsorge: {
    id: "vorsorge",
    persona: "stefan",
    messages: [
      { text: "Ich bin selbstständig und möchte etwas für meine Gesundheit tun. Was bietet mir meine Versicherung an?" },
      { text: "Ich möchte mich mehr bewegen und weniger Stress haben. Meine letzte Vorsorgeuntersuchung ist über drei Jahre her." },
      { text: "Wo kann ich die Vorsorgeuntersuchung in 1100 machen? Bitte schlag mir einen Termin bei der Demo-Ordination vor." },
      { text: "Bitte leg mir die nächsten Schritte in Mein Fall an." },
    ],
  },
};

/** Ctrl+Shift+<digit> selects a script. `KeyboardEvent.code` ignores the keyboard layout. */
export const SCRIPT_SHORTCUTS: Readonly<Record<string, ScriptId>> = {
  Digit1: "golden",
  Digit2: "kopfschmerz",
  Digit3: "pflegegeld",
  Digit4: "vorsorge",
  Digit5: "englisch",
};

const PERSONA_DEFAULTS: Readonly<Record<string, ScriptId>> = {
  maria: "pflegegeld",
  stefan: "kopfschmerz",
  elif: "englisch",
};

/** The selected script if it fits the persona, else the persona's default script. */
export function scriptFor(selected: ScriptId | null, persona: string): DemoScript | null {
  if (selected && SCRIPTS[selected].persona === persona) return SCRIPTS[selected];
  const fallback = PERSONA_DEFAULTS[persona];
  return fallback ? SCRIPTS[fallback] : null;
}

/** The first script message not yet sent in this conversation. Hand-typed steps count too. */
export function nextMessage(script: DemoScript, sent: readonly string[]): ScriptMessage | null {
  const done = new Set(sent.map((content) => content.trim()));
  return script.messages.find((message) => !done.has(message.text)) ?? null;
}

const ALARM_WORDS = ["plötzlich", "stark", "unerträglich", "sturz", "unfall", "fieber"];

/** Port of `pick_option` in record_demo.py, so the click matches the recorded answer. */
export function pickSamplerOption(options: readonly string[], keywords: readonly string[] = []): string | null {
  for (const keyword of keywords) {
    const hit = options.find((option) => option.toLowerCase().includes(keyword));
    if (hit) return hit;
  }
  // Never fall back to an alarm sign: the story is a mild tension headache.
  const calm = options.filter((option) => !ALARM_WORDS.some((word) => option.toLowerCase().includes(word)));
  const unsure = calm.filter((option) => /weiß|weiss/.test(option.toLowerCase()));
  return unsure[0] ?? calm[0] ?? options[0] ?? null;
}
