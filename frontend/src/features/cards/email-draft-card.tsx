"use client";

import { useId, useState } from "react";
import { ClipboardCheck, Mail, Send } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CardOf } from "@/lib/api";

import { CopyButton, ResultCardFrame } from "./result-cards";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const isEmailAddress = (value: string) => EMAIL.test(value.trim());

/** A mailto link for the person's own mail program. An invalid address stays out. */
export function mailtoHref(to: string, subject: string, body: string): string {
  const address = isEmailAddress(to) ? to.trim() : "";
  return `mailto:${address}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

export type EmailDraftCardProps = { card: CardOf<"email_draft"> };

/** The person checks, edits and sends the e-mail. The Lotse never sends it. */
export function EmailDraftCard({ card: { email } }: EmailDraftCardProps) {
  const [to, setTo] = useState(email.to_email ?? "");
  const [subject, setSubject] = useState(email.subject);
  const [body, setBody] = useState(email.body);
  const toId = useId();
  const subjectId = useId();
  const bodyId = useId();
  const hintId = useId();
  const invalid = to.trim() !== "" && !isEmailAddress(to);

  return <ResultCardFrame title="E-Mail-Entwurf" icon={Mail}
    badge={<Badge variant="caution"><ClipboardCheck aria-hidden />Von Ihnen zu prüfen</Badge>}>
    <p><span className="text-text-secondary">An: </span><span className="text-label">{email.to_label}</span></p>
    <div className="space-y-2">
      <Label htmlFor={toId}>E-Mail-Adresse</Label>
      <Input id={toId} type="email" inputMode="email" autoComplete="off" value={to}
        aria-invalid={invalid || undefined} aria-describedby={hintId}
        onChange={event => setTo(event.target.value)} />
      <p id={hintId} className="text-caption text-text-secondary">
        {invalid ? "Bitte prüfen Sie die E-Mail-Adresse." : "Tragen Sie die Adresse selbst ein. Der Lotse kennt sie nicht."}
      </p>
    </div>
    <div className="space-y-2">
      <Label htmlFor={subjectId}>Betreff</Label>
      <Input id={subjectId} value={subject} onChange={event => setSubject(event.target.value)} />
    </div>
    <div className="space-y-2">
      <Label htmlFor={bodyId}>Nachricht</Label>
      <Textarea id={bodyId} rows={8} value={body} onChange={event => setBody(event.target.value)} />
    </div>
    <div className="flex flex-wrap items-start gap-3">
      <Button asChild>
        <a href={mailtoHref(to, subject, body)}><Send />In E-Mail-Programm öffnen</a>
      </Button>
      <CopyButton value={`Betreff: ${subject}\n\n${body}`} label="Text kopieren"
        doneMessage="E-Mail-Text kopiert."
        errorDescription="Markieren Sie den Text und kopieren Sie ihn selbst." />
    </div>
    <p className="text-caption text-text-secondary">Der Lotse sendet keine E-Mails. Sie prüfen den Text und senden ihn selbst.</p>
  </ResultCardFrame>;
}
