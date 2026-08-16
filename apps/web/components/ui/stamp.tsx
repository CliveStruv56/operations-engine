import type { ReactNode } from "react";

/**
 * Hearth's pill badge. Tones map to the palette's jobs, which is why there is
 * no "info" or "brand" tone: `grounded` is reserved for trust states (vault
 * connected, grounded answers) and must not become a general-purpose green.
 *
 * Every tone carries a word. Colour never states the condition on its own —
 * a red dot with no label is unreadable to anyone who cannot see red.
 */
const TONES = {
  /** Ordinary metadata: counts, categories, stages. */
  neutral: "bg-sidebar text-subtle",
  /** Terracotta wash. The non-urgent highlight; counts against nothing. */
  accent: "border border-electric-blue/25 bg-accent-tint text-electric-blue",
  /** Trust only: vault connected, answer grounded, identity verified. */
  grounded: "bg-grounded-tint text-grounded",
  /** Needs attention but nothing is broken: overdue, stale, parsing. */
  warn: "bg-warn-soft text-warn",
  /** Something failed or will be destroyed. */
  danger: "bg-danger-soft text-danger",
} as const;

export type StampTone = keyof typeof TONES;

export function Stamp({
  tone = "neutral",
  dot = false,
  children,
  className = "",
}: {
  tone?: StampTone;
  /** Leading dot, as on the vault chip. Decorative — the label carries it. */
  dot?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={`stamp inline-flex items-center gap-1.5 ${TONES[tone]} ${className}`}>
      {dot && <i aria-hidden="true" className="h-[6px] w-[6px] rounded-full bg-current" />}
      {children}
    </span>
  );
}
