"use client";

import { motion, useReducedMotion } from "framer-motion";
import {
  BellRing, CalendarDays, ChevronLeft, ChevronRight, Clock, MapPin, Maximize2, Minimize2, Plus, Stethoscope, Trash2, X,
  type LucideIcon,
} from "lucide-react";
import { useId, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/state";
import type { CalendarEntry, CalendarKind } from "@/lib/api";
import { cn } from "@/lib/utils";

import { useCalendar } from "./calendar-context";
import {
  dayKey, dayNumber, formatTime, isUpcoming, longDay, monthGrid, monthShort, monthTitle, viennaInstant, weekdayShort,
} from "./dates";

const EASE_OUT: [number, number, number, number] = [0.2, 0, 0, 1];
/** Minimized panel: the next dates only. */
const PREVIEW_COUNT = 3;

const kinds: Record<CalendarKind, { label: string; icon: LucideIcon; badge: "accent" | "caution" | "neutral" }> = {
  appointment: { label: "Termin", icon: Stethoscope, badge: "accent" },
  deadline: { label: "Frist", icon: Clock, badge: "caution" },
  other: { label: "Erinnerung", icon: BellRing, badge: "neutral" },
};

const weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

/**
 * „Kalender“ under „Mein Fall“. Minimized it lists the next dates.
 * Maximized it fills the column with a month view, all dates and a form for new dates.
 * Content only: AppShell places it and hides „Mein Fall“ while it is maximized.
 */
export function CalendarPanel() {
  const calendar = useCalendar();
  const reduce = useReducedMotion();
  const [expanded, setExpanded] = useState(false);
  const [startAdding, setStartAdding] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const headingId = useId();

  const upcoming = useMemo(() => calendar?.entries.filter((entry) => isUpcoming(entry)) ?? [], [calendar?.entries]);
  if (!calendar) return null;

  function setSize(next: boolean, adding = false) {
    setExpanded(next);
    setStartAdding(adding);
    // The form takes focus itself.
    if (adding) return;
    // Keep focus on the toggle, so keyboard users do not lose their place.
    requestAnimationFrame(() => toggleRef.current?.focus());
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape" && expanded) {
      event.stopPropagation();
      setSize(false);
    }
  }

  return (
    <motion.section
      layout={!reduce}
      transition={{ duration: 0.25, ease: EASE_OUT }}
      aria-labelledby={headingId}
      data-calendar={expanded ? "expanded" : "collapsed"}
      onKeyDown={onKeyDown}
      className={cn("glass flex min-h-0 flex-col overflow-hidden rounded-xl text-text shadow-card", expanded ? "flex-1" : "shrink-0")}
    >
      <motion.div layout={reduce ? false : "position"} className="flex items-center gap-2 border-b px-4 py-3 beamer:px-6">
        <CalendarDays aria-hidden className="size-5 shrink-0" />
        <h2 id={headingId} className="text-heading">Kalender</h2>
        {calendar.status === "ready"
          ? <Badge variant="neutral" className="tabular">{upcoming.length} bevorstehend</Badge> : null}
        <Button ref={toggleRef} variant="ghost" size="icon-sm" className="ms-auto" aria-expanded={expanded}
          aria-label={expanded ? "Kalender verkleinern" : "Kalender vergrößern"} onClick={() => setSize(!expanded)}>
          {expanded ? <Minimize2 /> : <Maximize2 />}
        </Button>
      </motion.div>

      {calendar.status === "loading" ? <div aria-hidden className="space-y-3 p-4">
        {[0, 1].map((index) => <Skeleton key={index} className="h-14 w-full" />)}
      </div>
        : calendar.status === "error" ? <div className="p-4">
          <ErrorState title="Ihr Kalender konnte nicht geladen werden." onRetry={calendar.reload} />
        </div>
        : expanded ? <ExpandedView upcoming={upcoming} startAdding={startAdding} />
        : <CollapsedView upcoming={upcoming} onShowAll={() => setSize(true)} onAdd={() => setSize(true, true)} />}
      <p role="status" className="sr-only">{calendar.status === "loading" ? "Kalender wird geladen…" : ""}</p>
    </motion.section>
  );
}

function CollapsedView({ upcoming, onShowAll, onAdd }: { upcoming: CalendarEntry[]; onShowAll: () => void; onAdd: () => void }) {
  if (!upcoming.length) {
    return <div className="flex flex-col items-start gap-2 p-4">
      <p className="text-body text-text-secondary">Keine bevorstehenden Termine.</p>
      <Button variant="secondary" size="sm" onClick={onAdd}><Plus />Termin eintragen</Button>
    </div>;
  }
  const rest = upcoming.length - PREVIEW_COUNT;
  return <div className="px-4 py-2 beamer:px-6">
    <ol aria-label="Nächste Termine" className="divide-y divide-border">
      {upcoming.slice(0, PREVIEW_COUNT).map((entry) => <li key={entry.id}><EntryRow entry={entry} compact /></li>)}
    </ol>
    {rest > 0 ? <Button variant="link" className="mb-1" onClick={onShowAll}>
      {rest === 1 ? "1 weiterer Termin" : `${rest} weitere Termine`}
    </Button> : null}
  </div>;
}

function ExpandedView({ upcoming, startAdding }: { upcoming: CalendarEntry[]; startAdding: boolean }) {
  const calendar = useCalendar()!;
  const today = dayKey(new Date());
  const [view, setView] = useState(() => ({ year: Number(today.slice(0, 4)), month: Number(today.slice(5, 7)) - 1 }));
  const [selected, setSelected] = useState<string | null>(null);
  const [adding, setAdding] = useState(startAdding);

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEntry[]>();
    for (const entry of calendar.entries) {
      const key = dayKey(entry.start);
      map.set(key, [...(map.get(key) ?? []), entry]);
    }
    return map;
  }, [calendar.entries]);

  const groups = useMemo(() => {
    const shown = selected ? byDay.get(selected) ?? [] : upcoming;
    const result: { key: string; entries: CalendarEntry[] }[] = [];
    for (const entry of shown) {
      const key = dayKey(entry.start);
      const last = result.at(-1);
      if (last?.key === key) last.entries.push(entry);
      else result.push({ key, entries: [entry] });
    }
    return result;
  }, [selected, byDay, upcoming]);

  function move(step: number) {
    setView(({ year, month }) => {
      const next = month + step;
      return { year: year + Math.floor(next / 12), month: ((next % 12) + 12) % 12 };
    });
  }

  function onSaved(entry: CalendarEntry) {
    setAdding(false);
    const key = dayKey(entry.start);
    setSelected(key);
    setView({ year: Number(key.slice(0, 4)), month: Number(key.slice(5, 7)) - 1 });
  }

  const title = monthTitle.format(new Date(Date.UTC(view.year, view.month, 1)));
  return <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 beamer:p-6">
    {adding ? <EntryForm defaultDate={selected ?? today} onCancel={() => setAdding(false)} onSaved={onSaved} />
      : <Button variant="secondary" className="w-full" onClick={() => setAdding(true)}><Plus />Termin eintragen</Button>}

    <div className="mt-6 flex items-center gap-2">
      <Button variant="ghost" size="icon-sm" aria-label="Vorheriger Monat" onClick={() => move(-1)}><ChevronLeft /></Button>
      <h3 className="flex-1 text-center text-label" aria-live="polite">{title}</h3>
      <Button variant="ghost" size="icon-sm" aria-label="Nächster Monat" onClick={() => move(1)}><ChevronRight /></Button>
    </div>
    <div className="mt-2 grid grid-cols-7 gap-1 text-center">
      <div aria-hidden className="contents">
        {weekdays.map((day) => <span key={day} className="py-1 text-caption text-text-secondary">{day}</span>)}
      </div>
      <div role="group" aria-label={`Tage im ${title}`} className="contents">
        {monthGrid(view.year, view.month).map((cell, index) => {
          if (!cell) return <span key={`lead-${index}`} aria-hidden />;
          const count = byDay.get(cell.key)?.length ?? 0;
          const isSelected = selected === cell.key;
          const isToday = cell.key === today;
          const label = `${longDay.format(new Date(`${cell.key}T12:00:00Z`))}${count ? `, ${count} ${count === 1 ? "Eintrag" : "Einträge"}` : ""}`;
          return <span key={cell.key}>
            <button type="button" aria-label={label} aria-pressed={isSelected}
              aria-current={isToday ? "date" : undefined}
              onClick={() => setSelected(isSelected ? null : cell.key)}
              className={cn(
                "relative flex h-10 w-full flex-col items-center justify-center rounded-md text-body tabular outline-none transition-[background-color,color] duration-150 ease-out focus-visible:ring-2 focus-visible:ring-ring",
                isSelected ? "bg-accent-solid text-on-accent" : "hover:bg-muted",
                isToday && !isSelected && "font-semibold text-accent-text ring-1 ring-accent-border",
                cell.key < today && !isSelected && "text-text-secondary",
              )}>
              {cell.day}
              {count ? <span aria-hidden className={cn("absolute bottom-1 size-1.5 rounded-full", isSelected ? "bg-on-accent" : "bg-accent-solid")} /> : null}
            </button>
          </span>;
        })}
      </div>
    </div>

    <div className="mt-6 flex items-center gap-2">
      <h3 className="flex-1 text-heading">
        {selected ? longDay.format(new Date(`${selected}T12:00:00Z`)) : "Alle bevorstehenden Termine"}
      </h3>
      {selected ? <Button variant="ghost" size="sm" onClick={() => setSelected(null)}><X />Alle zeigen</Button> : null}
    </div>
    {groups.length ? <ol className="mt-2 space-y-4">
      {groups.map((group) => <li key={group.key}>
        {selected ? null : <p className="text-caption text-text-secondary">{longDay.format(new Date(`${group.key}T12:00:00Z`))}</p>}
        <ul className="divide-y divide-border">
          {group.entries.map((entry) => <li key={entry.id}><EntryRow entry={entry} deletable /></li>)}
        </ul>
      </li>)}
    </ol> : <p className="mt-2 text-body text-text-secondary">
      {selected ? "An diesem Tag ist nichts eingetragen." : "Keine bevorstehenden Termine."}
    </p>}
    <p className="mt-6 text-caption text-text-secondary">
      Der Kalender erinnert Sie nur. Termine bei Ärztinnen und Ärzten vereinbaren Sie selbst.
    </p>
  </div>;
}

function EntryRow({ entry, deletable = false, compact = false }: { entry: CalendarEntry; deletable?: boolean; compact?: boolean }) {
  const calendar = useCalendar();
  const [deleting, setDeleting] = useState(false);
  const kind = kinds[entry.kind];
  const start = new Date(entry.start);

  async function remove() {
    if (!calendar || deleting) return;
    setDeleting(true);
    try {
      await calendar.remove(entry.id);
    } catch {
      toast.error("Der Eintrag wurde nicht gelöscht.", { description: "Bitte versuchen Sie es erneut." });
      setDeleting(false);
    }
  }

  if (compact) {
    return <div className="flex items-center gap-3 py-2">
      <div aria-hidden className="flex w-10 shrink-0 flex-col items-center rounded-md bg-accent-subtle py-0.5 text-accent-text">
        <span className="text-caption">{weekdayShort.format(start)}</span>
        <span className="text-label tabular">{dayNumber.format(start)}</span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-label" title={entry.title}>
          <span className="sr-only">{longDay.format(start)}: </span>{entry.title}
        </p>
        <p className="flex items-center gap-1 text-caption text-text-secondary tabular">
          <kind.icon aria-hidden className={cn("size-3.5 shrink-0", entry.kind === "deadline" ? "text-caution-text" : entry.kind === "appointment" ? "text-accent-text" : "")} />
          {kind.label} · {formatTime(entry)}
        </p>
      </div>
    </div>;
  }
  return <div className="flex items-start gap-3 py-3">
    <div aria-hidden className="flex w-12 shrink-0 flex-col items-center rounded-md bg-accent-subtle py-1 text-accent-text">
      <span className="text-caption">{weekdayShort.format(start)}</span>
      <span className="text-heading tabular">{dayNumber.format(start)}</span>
      <span className="text-caption">{monthShort.format(start)}</span>
    </div>
    <div className="min-w-0 flex-1 space-y-1">
      <p className="text-label text-pretty wrap-break-word">
        <span className="sr-only">{longDay.format(start)}: </span>{entry.title}
      </p>
      <p className="text-caption text-text-secondary tabular">{formatTime(entry)}</p>
      {entry.location ? <p className="flex items-start gap-1 text-caption text-text-secondary">
        <MapPin aria-hidden className="mt-0.5 size-3.5 shrink-0" />{entry.location}
      </p> : null}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <Badge variant={kind.badge}><kind.icon aria-hidden />{kind.label}</Badge>
        {entry.conversation_id && entry.conversation_id === calendar?.conversationId
          ? <span className="text-caption text-text-secondary">Aus diesem Gespräch</span> : null}
      </div>
    </div>
    {deletable ? <Button variant="ghost" size="icon-sm" disabled={deleting} aria-label={`Eintrag löschen: ${entry.title}`}
      onClick={() => void remove()}><Trash2 /></Button> : null}
  </div>;
}

function EntryForm({ defaultDate, onCancel, onSaved }: {
  defaultDate: string; onCancel: () => void; onSaved: (entry: CalendarEntry) => void;
}) {
  const calendar = useCalendar()!;
  const id = useId();
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<CalendarKind>("appointment");
  const [date, setDate] = useState(defaultDate);
  const [time, setTime] = useState("");
  const [location, setLocation] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const canSave = title.trim().length > 0 && /^\d{4}-\d{2}-\d{2}$/.test(date) && !saving;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSave) return;
    setSaving(true);
    setError(false);
    try {
      const saved = await calendar.add({
        kind, title: title.trim(), start: viennaInstant(date, time || "00:00"), all_day: !time,
        location: location.trim() || null, conversation_id: calendar.conversationId ?? null,
      });
      toast("Im Kalender gespeichert.");
      onSaved(saved);
    } catch {
      setError(true);
      setSaving(false);
    }
  }

  return <form onSubmit={(event) => void submit(event)} className="space-y-4 rounded-lg border border-border-strong bg-surface p-4"
    aria-label="Neuer Kalendereintrag">
    <div className="space-y-2">
      <Label htmlFor={`${id}-title`}>Was steht an?</Label>
      <Input id={`${id}-title`} value={title} required maxLength={200} autoFocus
        placeholder="z. B. Kontrolle bei der Hausärztin" onChange={(event) => setTitle(event.target.value)} />
    </div>
    <fieldset className="space-y-2">
      <legend className="text-label">Art</legend>
      <div className="flex flex-wrap gap-2">
        {(Object.keys(kinds) as CalendarKind[]).map((value) => {
          const checked = kind === value;
          const Icon = kinds[value].icon;
          return <label key={value} className={cn(
            "relative inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border px-3 text-label transition-[background-color,border-color,color] duration-150 ease-out has-focus-visible:ring-2 has-focus-visible:ring-ring",
            checked ? "border-accent-solid bg-accent-subtle text-accent-text" : "border-border-strong bg-surface text-text hover:bg-muted",
          )}>
            <input type="radio" name={`${id}-kind`} value={value} checked={checked} onChange={() => setKind(value)} className="sr-only" />
            <Icon aria-hidden className="size-4" />{kinds[value].label}
          </label>;
        })}
      </div>
    </fieldset>
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <Label htmlFor={`${id}-date`}>Datum</Label>
        <Input id={`${id}-date`} type="date" required value={date} onChange={(event) => setDate(event.target.value)} />
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${id}-time`}>Uhrzeit</Label>
        <Input id={`${id}-time`} type="time" value={time} aria-describedby={`${id}-time-hint`}
          onChange={(event) => setTime(event.target.value)} />
      </div>
    </div>
    <p id={`${id}-time-hint`} className="-mt-2 text-caption text-text-secondary">Ohne Uhrzeit gilt der Eintrag für den ganzen Tag.</p>
    <div className="space-y-2">
      <Label htmlFor={`${id}-location`}>Ort <span className="text-text-secondary">(optional)</span></Label>
      <Input id={`${id}-location`} value={location} maxLength={300} onChange={(event) => setLocation(event.target.value)} />
    </div>
    {error ? <ErrorState title="Der Eintrag wurde nicht gespeichert." /> : null}
    <div className="flex flex-wrap gap-2">
      <Button type="submit" disabled={!canSave}>{saving ? "Wird gespeichert…" : "Speichern"}</Button>
      <Button type="button" variant="ghost" onClick={onCancel}>Abbrechen</Button>
    </div>
  </form>;
}
