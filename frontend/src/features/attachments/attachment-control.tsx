"use client";

import { CircleCheck, FileText, Loader2, Paperclip, RotateCcw, X } from "lucide-react";
import { useId, useRef } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/state";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Document, DocumentStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

/** `processing` uses the API status. Only `uploading` precedes an API document. */
export type AttachmentPhase = "uploading" | DocumentStatus;

export type AttachmentChipProps = {
  filename: Document["filename"];
  phase: AttachmentPhase;
  documentId?: Document["id"] | null;
  /** A readable German message from the controller, never a raw exception. */
  error?: string | null;
  onRemove: () => void;
  onRetry: () => void;
  className?: string;
};

export type AttachmentControlProps = {
  /** `null` means no attachment. The parent owns all attachment state. */
  filename?: Document["filename"] | null;
  phase?: AttachmentPhase | null;
  documentId?: Document["id"] | null;
  error?: string | null;
  onFileSelected: (file: File) => void;
  onRemove: () => void;
  onRetry: () => void;
  className?: string;
};

const labels: Record<AttachmentPhase, string> = {
  uploading: "Wird hochgeladen…",
  processing: "Wird gelesen…",
  ready: "Bereit",
  failed: "Fehlgeschlagen",
};

/** Presentation only. Removing stays available during every phase, including failure. */
export function AttachmentChip({
  filename, phase, documentId, error, onRemove, onRetry, className,
}: AttachmentChipProps) {
  const busy = phase === "uploading" || phase === "processing";
  const StatusIcon = phase === "ready" ? CircleCheck : busy ? Loader2 : FileText;

  return (
    <div
      role="group"
      aria-label={`Anhang: ${filename}`}
      data-document-id={documentId ?? undefined}
      className={cn("flex min-w-0 flex-col gap-3 rounded-lg border bg-surface p-3", className)}
    >
      <div className="flex min-w-0 items-center gap-3">
        <FileText aria-hidden className="size-5 shrink-0 text-text-secondary" strokeWidth={1.5} />
        <div className="min-w-0 flex-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0} className="block truncate rounded-sm text-label text-text">
                <bdi>{filename}</bdi>
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-answer break-all">{filename}</TooltipContent>
          </Tooltip>
          <p role="status" aria-atomic="true" className={cn(
            "flex items-center gap-2 text-caption text-text-secondary",
            phase === "ready" && "text-accent-text",
          )}>
            <StatusIcon aria-hidden className="size-4 shrink-0" strokeWidth={1.5} />
            <span>{labels[phase]}</span>
          </p>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onRemove} aria-label={`Entfernen: ${filename}`}>
          <X />
        </Button>
      </div>
      {phase === "failed" ? (
        <>
          <ErrorState
            title="Dokument konnte nicht gelesen werden."
            description={error || "Bitte versuchen Sie es erneut oder entfernen Sie das Dokument."}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={onRetry} aria-label={`Erneut versuchen: ${filename}`}>
              <RotateCcw />Erneut versuchen
            </Button>
            <Button type="button" variant="secondary" onClick={onRemove}>
              Ohne Dokument fortfahren
            </Button>
          </div>
          <p className="text-caption text-text-secondary">
            Sie können das Dokument entfernen und Ihre Nachricht ohne Dokument senden.
          </p>
        </>
      ) : null}
    </div>
  );
}

/** Opens the native picker. Does not upload, poll, submit, or retain selected files. */
export function AttachmentControl({
  filename, phase, documentId, error, onFileSelected, onRemove, onRetry, className,
}: AttachmentControlProps) {
  const input = useRef<HTMLInputElement>(null);
  const pickerButton = useRef<HTMLButtonElement>(null);
  const helpId = useId();

  return (
    <div className={cn("flex min-w-0 flex-col gap-3", className)}>
      {filename && phase ? (
        <AttachmentChip
          {...{ filename, phase, documentId, error, onRetry }}
          onRemove={() => {
            onRemove();
            // Keep keyboard focus in the composer after its chip disappears.
            pickerButton.current?.focus();
          }}
        />
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={input}
          type="file"
          hidden
          name="attachment"
          aria-label="Dokument auswählen"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            // Allow choosing the same file again after removal or a failed attempt.
            event.currentTarget.value = "";
            if (file) onFileSelected(file);
          }}
        />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              ref={pickerButton}
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Dokument anhängen"
              aria-describedby={helpId}
              onClick={() => input.current?.click()}
            >
              <Paperclip />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Dokument anhängen</TooltipContent>
        </Tooltip>
        <span id={helpId} className="text-caption text-text-secondary">PDF, JPEG oder PNG</span>
      </div>
    </div>
  );
}
