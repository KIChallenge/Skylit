import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/*
 * tailwind-merge must know the custom type scale from globals.css.
 * Otherwise it reads `text-label` as a colour and drops `text-primary-foreground`.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["display", "title", "heading", "answer", "body", "label", "caption"] }],
    },
  },
});

/** Merges Tailwind class names. shadcn/ui components use this helper. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
