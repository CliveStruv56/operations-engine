import type { ReactNode } from "react";
import { card as cardCls } from "./styles";

export function Card({
  children,
  className = "",
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return <div className={`${cardCls} ${padded ? "p-5" : ""} ${className}`}>{children}</div>;
}

/**
 * A titled region. The heading is Fraunces at 22px, which is the smallest size
 * Hearth allows the serif — below that it has to be Plus Jakarta.
 *
 * Fraunces currently appears in exactly one place in the whole product (the
 * chat greeting), which is why every screen below the chat reads the same. A
 * section title is the cheapest place to give a screen a voice.
 */
export function Section({
  title,
  kicker,
  description,
  action,
  children,
  className = "",
  as: Heading = "h2",
}: {
  title: string;
  /** Small uppercase accent line above the title. Sparse — one per band. */
  kicker?: string;
  description?: ReactNode;
  /** Sits opposite the title. One action, or an overflow. */
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
  as?: "h2" | "h3";
}) {
  return (
    <section className={className}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          {kicker && (
            <p className="data mb-1.5 text-electric-blue uppercase">{kicker}</p>
          )}
          <Heading className="font-display text-hearth-section leading-tight font-semibold tracking-[-0.025em]">
            {title}
          </Heading>
          {description && (
            <p className="mt-1.5 max-w-[60ch] text-sm text-subtle">{description}</p>
          )}
        </div>
        {action}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </section>
  );
}

/**
 * A tinted full-bleed band. Hearth ships a second surface (`--sidebar`) that
 * the app only ever uses for the sidebar itself, so long screens are one
 * unbroken run of white cards on cream. Alternating a band in gives a screen
 * sections you can feel without adding a colour.
 */
export function Band({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`border-y border-edge bg-band ${className}`}>
      <div className="mx-auto max-w-3xl px-6 py-7">{children}</div>
    </div>
  );
}
