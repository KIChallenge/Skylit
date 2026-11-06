import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

/*
 * Every state badge carries an icon and a text label. Colour is never the only signal.
 * accent  = „Sicherheit: hoch", „Erledigt"
 * caution = „Sicherheit: mittel", „Von Ihnen zu prüfen", Übergabe
 * caution-strong = „Sicherheit: niedrig"
 * emergency = „Notfall" only
 */
const badgeVariants = cva(
  "inline-flex w-fit max-w-full shrink-0 items-center justify-center gap-1 rounded-full border px-2.5 py-0.5 text-caption font-semibold whitespace-normal break-words [&>svg]:pointer-events-none [&>svg]:size-3.5 [&>svg]:shrink-0 [&>svg]:stroke-2",
  {
    variants: {
      variant: {
        neutral: "border-border bg-subtle text-text",
        outline: "border-border-strong bg-surface text-text",
        accent: "border-accent-border bg-accent-subtle text-accent-text",
        caution: "border-caution-border bg-caution-subtle text-caution-text",
        "caution-strong": "border-transparent bg-caution-solid text-on-caution",
        emergency: "border-transparent bg-emergency-solid text-on-emergency",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  }
)

function Badge({
  className,
  variant = "neutral",
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
