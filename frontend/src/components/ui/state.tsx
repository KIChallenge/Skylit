import { CircleAlert, RotateCcw, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type StateProps = {
  title: string;
  description?: ReactNode;
  className?: string;
};

/** Empty state: icon, one calm sentence, optional action. */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: StateProps & { icon: LucideIcon; action?: ReactNode }) {
  return (
    <div className={cn("flex flex-col items-center gap-3 px-6 py-10 text-center", className)}>
      <span className="flex size-12 items-center justify-center rounded-full bg-accent-subtle text-accent-text">
        <Icon aria-hidden className="size-6" strokeWidth={1.5} />
      </span>
      <p className="text-heading text-text">{title}</p>
      {description ? <p className="max-w-prose text-body text-pretty text-text-secondary">{description}</p> : null}
      {action}
    </div>
  );
}

/**
 * Error state with „Erneut versuchen". Neutral with a strong edge: red is only for emergencies.
 * Never shows a raw error or stack trace.
 */
export function ErrorState({
  title = "Das hat nicht geklappt.",
  description = "Bitte versuchen Sie es erneut.",
  onRetry,
  retryLabel = "Erneut versuchen",
  className,
}: Partial<StateProps> & { onRetry?: () => void; retryLabel?: string }) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-lg border-2 border-border-strong bg-surface p-4",
        className,
      )}
    >
      <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-text" strokeWidth={2} />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="text-label text-text">{title}</p>
        {description ? <p className="text-body text-pretty text-text-secondary">{description}</p> : null}
        {onRetry ? (
          <div className="pt-2">
            <Button variant="secondary" size="sm" onClick={onRetry}>
              <RotateCcw />
              {retryLabel}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
