"use client"

import {
  CircleAlertIcon,
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  TriangleAlertIcon,
} from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

/* Light theme only. Errors use a neutral icon: red is reserved for emergencies. */
const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="light"
      position="bottom-center"
      className="toaster group"
      icons={{
        success: <CircleCheckIcon className="size-4 text-accent-text" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4 text-caution-text" />,
        error: <CircleAlertIcon className="size-4" />,
        loading: <Loader2Icon className="size-4 motion-safe:animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--bg-surface)",
          "--normal-text": "var(--text)",
          "--normal-border": "var(--border-strong)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
