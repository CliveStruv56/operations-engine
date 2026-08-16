import type { ReactNode } from "react";

/**
 * The pill badge. Tones map to the palette's jobs, which is why there is
 * no "info" or "brand" tone: `grounded` is reserved for trust states (vault
 * connected, grounded answers) and must not become a general-purpose green.
 *
 * The pastel tones are the Huddle status taxonomy and keep a fixed meaning:
 * sage = upcoming/monitoring, lavender = in progress (`active` is the same
 * tile lifted by deep-violet text), rose = shipped/complete. Don't reassign
 * them decoratively — swapping the colours breaks the categorical code.
 *
 * Every tone carries a word. Colour never states the condition on its own —
 * a red dot with no label is unreadable to anyone who cannot see red.
 */
const TONES = {
  /** Ordinary metadata: counts, categories, stages. */
  neutral: "bg-sidebar text-subtle",
  /** Lavender wash with deep-violet type. The non-urgent highlight. */
  accent: "border border-electric-blue/25 bg-accent-tint text-electric-blue",
  /** Trust only: vault connected, answer grounded, identity verified. */
  grounded: "bg-grounded-tint text-grounded",
  /** Needs attention but nothing is broken: overdue, stale, parsing. */
  warn: "bg-warn-soft text-warn",
  /** Something failed or will be destroyed. */
  danger: "bg-danger-soft text-danger",
  /** Status taxonomy — upcoming, monitored, in pipeline. */
  sage: "border border-stone/50 bg-pale-sage text-ink",
  /** Status taxonomy — in progress, building, submitted. */
  lavender: "border border-stone/50 bg-lavender-mist text-ink",
  /** Status taxonomy — the live one; lavender tile, deep-violet type. */
  active: "border border-stone/50 bg-lavender-mist text-deep-violet",
  /** Status taxonomy — shipped, awarded, complete. */
  rose: "border border-stone/50 bg-dusty-rose text-ink",
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
