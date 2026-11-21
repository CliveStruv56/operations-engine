import Link from "next/link";
import { DemoAgendaPanel } from "./cta-panels";
import {
  AUDIENCES,
  AUDIENCES_TITLE,
  BUILT_NEXT,
  CLOSING,
  IN_CHARGE,
  TRUST,
  WORKS_TODAY,
  type RichLine,
} from "./home-content";
import { Spot } from "./spot-icons";
import { ctaGhost, ctaOutline, DemoCta, Section } from "./ui";

/* Home page sections (consultancy-first rewrite, Nov 2026). All copy comes
 * from home-content.ts; this file is layout only, so page.tsx stays a
 * readable outline of the sections in order. */

const bandTitle =
  "mt-3 max-w-3xl text-[29px] font-normal leading-[1.3] tracking-[-0.32px] text-ink md:text-[40px] md:leading-[1.22] md:tracking-[-0.48px]";

const cardTitle = "text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink";

/** Status label in the StatusCard taxonomy: `active` (deep violet on
 * lavender) marks what works today; `neutral` (bone) marks planned work. */
function StatusLabel({ tone, children }: { tone: "active" | "neutral"; children: string }) {
  const look =
    tone === "active"
      ? "border-lavender-mist bg-lavender-mist text-deep-violet"
      : "border-edge-ui bg-bone text-ink";
  return (
    <p
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[12px] font-medium uppercase tracking-[0.08em] ${look}`}
    >
      <span
        aria-hidden
        className={
          tone === "active"
            ? "h-2 w-2 rounded-full bg-deep-violet"
            : "h-2 w-2 rounded-full border border-ink"
        }
      />
      {children}
    </p>
  );
}

/** Bulleted list. `trust` uses the grounded dot, kept for trust states. */
function DotList({
  items,
  tone = "neutral",
  className = "",
}: {
  items: string[];
  tone?: "trust" | "neutral";
  className?: string;
}) {
  const dot = tone === "trust" ? "bg-grounded" : "bg-slate";
  return (
    <ul className={className}>
      {items.map((line) => (
        <li key={line} className="flex gap-3 text-[16px] leading-[1.45] text-slate">
          <span aria-hidden className={`mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
          <span>{line}</span>
        </li>
      ))}
    </ul>
  );
}

export function AudiencesSection() {
  return (
    <Section title={AUDIENCES_TITLE}>
      <div className="grid gap-6 lg:grid-cols-3">
        {AUDIENCES.map((card) => (
          <div key={card.title} className="flex flex-col rounded-lg border border-bone p-6">
            <h3 className={cardTitle}>{card.title}</h3>
            <DotList items={card.points} className="mt-4 flex flex-1 flex-col gap-3" />
            <div className="mt-6 flex flex-wrap gap-3">
              {card.links.map((link) => (
                <Link key={link.href} href={link.href} className={ctaOutline}>
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

/* What works today — the page's one warm band (amber wash, marketing-only:
 * see workflow-diagram.tsx for why it isn't a globals.css token). */
export function WorksTodayBand() {
  return (
    <section
      id="works-today"
      aria-labelledby="works-today-title"
      className="scroll-mt-4 border-y border-bone bg-[#f2e9dc]"
    >
      <div className="mx-auto w-full max-w-[1200px] px-6 py-16">
        <StatusLabel tone="active">{WORKS_TODAY.label}</StatusLabel>
        <h2 id="works-today-title" className={bandTitle}>
          {WORKS_TODAY.title}
        </h2>
        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {WORKS_TODAY.cards.map((item) => (
            <div key={item.title} className="flex flex-col rounded-lg border border-bone bg-canvas p-6">
              <Spot name={item.spot} className="mb-4 h-auto w-full max-w-[220px]" />
              <h3 className={cardTitle}>{item.title}</h3>
              <p className="mt-3 text-[16px] leading-[1.45] text-slate">{item.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Rich({ line }: { line: RichLine }) {
  return (
    <>
      {line.map((part, i) =>
        part.strong ? (
          <strong key={i} className="font-medium text-ink">
            {part.text}
          </strong>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </>
  );
}

/* Being built next — deliberately unlike the band above: plain paper, a
 * dashed outline, hollow bullets, no icons and the "not available yet" label
 * first, so nobody reads a plan item as a product feature. */
export function BuiltNextSection() {
  return (
    <section aria-labelledby="built-next-title" className="mx-auto w-full max-w-[1200px] px-6 py-16">
      <div className="rounded-lg border border-dashed border-edge-ui p-6 md:p-10">
        <StatusLabel tone="neutral">{BUILT_NEXT.label}</StatusLabel>
        <h2 id="built-next-title" className={bandTitle}>
          {BUILT_NEXT.title}
        </h2>
        <p className="mt-4 max-w-2xl text-[18px] leading-[1.42] text-slate">{BUILT_NEXT.intro}</p>
        <ul className="mt-8 grid gap-5 md:grid-cols-3">
          {BUILT_NEXT.items.map((line, i) => (
            <li key={i} className="flex gap-3 text-[16px] leading-[1.45] text-slate">
              <span
                aria-hidden
                className="mt-[7px] h-2.5 w-2.5 shrink-0 rounded-full border border-slate"
              />
              <span>
                <Rich line={line} />
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function InChargeBand() {
  return (
    <section aria-labelledby="in-charge" className="border-y border-bone bg-band">
      <div className="mx-auto grid w-full max-w-[1200px] gap-10 px-6 py-16 lg:grid-cols-[5fr_7fr]">
        <h2 id="in-charge" className={bandTitle}>
          {IN_CHARGE.title}
        </h2>
        <DotList items={IN_CHARGE.points} tone="trust" className="flex flex-col gap-6 lg:pt-4" />
      </div>
    </section>
  );
}

/* No /security-and-data link here until Clive restores it (fact-check A22
 * and the copy's "Restore if Clive confirms" list). */
export function TrustBand() {
  return (
    <section aria-labelledby="trust" className="mx-auto w-full max-w-[1200px] px-6 py-16">
      <div className="grid gap-10 lg:grid-cols-[5fr_7fr]">
        <h2 id="trust" className={bandTitle}>
          {TRUST.title}
        </h2>
        <DotList items={TRUST.points} tone="trust" className="flex flex-col gap-6 lg:pt-4" />
      </div>
    </section>
  );
}

export function ClosingSection() {
  return (
    <section aria-labelledby="closing" className="border-t border-bone">
      <div className="mx-auto grid w-full max-w-[1200px] gap-12 px-6 py-16 lg:grid-cols-[7fr_5fr]">
        <div>
          <h2 id="closing" className={bandTitle}>
            {CLOSING.title}
          </h2>
          <p className="mt-6 max-w-2xl text-[18px] leading-[1.42] text-slate">{CLOSING.body}</p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            <DemoCta label={CLOSING.primaryCta} />
            <Link href={CLOSING.secondaryCta.href} className={ctaGhost}>
              {CLOSING.secondaryCta.label}
            </Link>
          </div>
        </div>
        <div>
          <DemoAgendaPanel />
        </div>
      </div>
    </section>
  );
}
