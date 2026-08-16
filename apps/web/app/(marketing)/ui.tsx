import Link from "next/link";
import type { ReactNode } from "react";

/* Marketing chrome primitives. Class strings follow the Huddle editorial
 * system already encoded in globals.css: hairline borders, no shadows,
 * pill CTAs, pastel status cards only where the status is real. */

export const ctaPrimary =
  "inline-flex min-h-[44px] items-center justify-center rounded-full bg-accent px-6 py-3 text-[16px] font-medium text-accent-ink transition-colors hover:bg-accent-deep";

export const ctaOutline =
  "inline-flex min-h-[44px] items-center justify-center rounded-full border border-ink px-5 py-2.5 text-[14px] font-medium text-ink transition-colors hover:bg-bone";

export const ctaGhost =
  "inline-flex min-h-[44px] items-center text-[16px] text-ink underline-offset-4 hover:underline";

export function Kicker({ children }: { children: ReactNode }) {
  return (
    <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
      <span aria-hidden>• </span>
      {children}
    </p>
  );
}

export function Section({
  kicker,
  title,
  children,
  className = "",
}: {
  kicker?: string;
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`mx-auto w-full max-w-[1200px] px-6 py-16 ${className}`}>
      {kicker && <Kicker>{kicker}</Kicker>}
      {title && (
        <h2 className="mt-3 max-w-3xl text-[29px] font-normal leading-[1.3] tracking-[-0.32px] text-ink md:text-[40px] md:leading-[1.22] md:tracking-[-0.48px]">
          {title}
        </h2>
      )}
      <div className={kicker || title ? "mt-10" : ""}>{children}</div>
    </section>
  );
}

export function TagPill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-burnt-amber px-3 py-1 text-[13px] font-medium text-burnt-amber">
      {children}
    </span>
  );
}

export function VioletPill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-deep-violet px-3 py-1 text-[13px] font-medium text-deep-violet">
      {children}
    </span>
  );
}

/* Pastel status card — the fixed taxonomy: sage = upcoming, lavender = in
 * progress (deep-violet text = active), rose = shipped/complete. */
export function StatusCard({
  tone,
  label,
  title,
  tags = [],
}: {
  tone: "sage" | "lavender" | "active" | "rose" | "neutral";
  label: string;
  title: string;
  tags?: string[];
}) {
  const bg =
    tone === "sage"
      ? "bg-pale-sage"
      : tone === "rose"
        ? "bg-dusty-rose"
        : tone === "neutral"
          ? "bg-bone"
          : "bg-lavender-mist";
  const text = tone === "active" ? "text-deep-violet" : "text-ink";
  return (
    <div className={`rounded-lg border border-stone p-6 ${bg}`}>
      <p className={`text-[12px] font-medium uppercase tracking-[0.08em] ${tone === "active" ? "text-deep-violet" : "text-slate"}`}>
        {label}
      </p>
      <p className={`mt-2 text-[22px] font-medium leading-[1.32] tracking-[-0.22px] ${text}`}>
        {title}
      </p>
      {tags.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {tags.map((t) => (
            <span
              key={t}
              className="inline-flex items-center rounded-full border border-burnt-amber bg-canvas px-3 py-1 text-[13px] font-medium text-burnt-amber"
            >
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function DemoCta({ label = "Book a demo" }: { label?: string }) {
  return (
    <Link href="/contact" className={ctaPrimary}>
      {label}
    </Link>
  );
}
