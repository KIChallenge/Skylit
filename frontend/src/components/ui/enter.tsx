"use client";

import { motion, useReducedMotion, type HTMLMotionProps } from "framer-motion";

/*
 * Entrance for new content (new card, new step in „Mein Fall").
 * better-ui: opacity, 12 px translateY, 4 px blur, 300 ms ease-out; stagger 100 ms via `index`.
 * Reduced motion: opacity only.
 */
const EASE_OUT: [number, number, number, number] = [0.2, 0, 0, 1];

export function Enter({
  index = 0,
  ...props
}: HTMLMotionProps<"div"> & { index?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 12, filter: "blur(4px)" }}
      animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0, filter: "blur(0px)" }}
      exit={reduce ? { opacity: 0 } : { opacity: 0, y: -12, filter: "blur(4px)", transition: { duration: 0.15, ease: EASE_OUT } }}
      transition={{ duration: 0.3, ease: EASE_OUT, delay: index * 0.1 }}
      {...props}
    />
  );
}
