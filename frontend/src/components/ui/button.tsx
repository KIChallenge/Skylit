import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

/*
 * One filled primary action per screen (variant "default").
 * Red ("emergency") is only for emergency calls (DESIGN.md §2).
 * Press: scale 0.96, 150 ms, ease-out; never when disabled (better-ui).
 */
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-label whitespace-nowrap select-none outline-none transition-[background-color,color,border-color,box-shadow,scale] duration-150 ease-out focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface active:not-disabled:not-aria-disabled:scale-96 disabled:pointer-events-none disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-70 motion-reduce:active:scale-100 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg]:stroke-2 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-accent-solid-hover",
        secondary:
          "border border-border-strong bg-surface text-text hover:bg-subtle",
        outline:
          "border border-border-strong bg-surface text-text hover:bg-subtle",
        ghost: "text-text hover:bg-muted",
        link: "h-auto px-0 text-accent-text underline underline-offset-4 hover:decoration-2 has-[>svg]:px-0",
        emergency:
          "bg-emergency-solid text-on-emergency hover:bg-emergency-solid-hover",
      },
      size: {
        default: "h-10 px-4 has-[>svg]:px-3.5",
        sm: "h-8 gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-12 px-5 text-body font-semibold has-[>svg]:px-4",
        icon: "size-10",
        "icon-sm": "size-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
