import { Circle, CircleCheck, CircleDot, CircleSlash } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { CaseStepStatus } from "@/lib/api";

const statuses = {
  open: { label: "Offen", icon: Circle, variant: "neutral" },
  in_progress: { label: "In Arbeit", icon: CircleDot, variant: "neutral" },
  done: { label: "Erledigt", icon: CircleCheck, variant: "accent" },
  blocked: { label: "Blockiert", icon: CircleSlash, variant: "caution" },
} as const;

export function StepStatusBadge({ status }: { status: CaseStepStatus }) {
  const { label, icon: Icon, variant } = statuses[status];
  return <Badge variant={variant}><Icon aria-hidden className="size-4" strokeWidth={2} />{label}</Badge>;
}
