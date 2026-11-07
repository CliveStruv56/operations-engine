import Link from "next/link";
import {
  AUDIENCES,
  CAPABILITIES,
  COSTS,
  FIGURES,
  IN_CHARGE,
  TRUST,
} from "./home-content";
import { Spot } from "./spot-icons";
import { ctaGhost, ctaOutline, Kicker, Section } from "./ui";

/* Home page sections (Nov 2026 rewrite). Kept out of page.tsx so the page
 * file stays a readable outline of the sections in order. */

const bandTitle =
  "mt-3 max-w-3xl text-[29px] font-normal leading-[1.3] tracking-[-0.32px] text-ink md:text-[40px] md:leading-[1.22] md:tracking-[-0.48px]";

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

/* What it does — the page's one warm band (amber wash, marketing-only: see
 * workflow-diagram.tsx for why it isn't a globals.css token). */
export function CapabilitiesBand() {
  return (
    <section
      aria-labelledby="what-it-does"
      className="border-b border-bone bg-[#f2e9dc]"
    >
      <div className="mx-auto w-full max-w-[1200px] px-6 py-16">
        <Kicker>What it does</Kicker>
        <h2 id="what-it-does" className={bandTitle}>
          One workspace, from the question to the finished document
        </h2>
        <p className="mt-4 max-w-2xl text-[18px] leading-[1.42] text-slate">
          Six things your team can do, in one place.
        </p>
        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map((item) => (
            <div key={item.title} className="flex flex-col rounded-lg border border-bone bg-canvas p-6">
              <Spot name={item.spot} className="mb-4 h-auto w-full max-w-[220px]" />
              <h3 className="text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink">
                {item.title}
              </h3>
              <p className="mt-3 text-[16px] leading-[1.45] text-slate">{item.body}</p>
              {item.also && (
                <div className="mt-4 border-t border-bone pt-4">
                  <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
                    Also
                  </p>
                  <ul className="mt-2 flex flex-col gap-2">
                    {item.also.map((line) => (
                      <li key={line} className="text-[15px] leading-[1.5] text-slate">
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
        <h3 className="mt-12 border-t border-bone pt-10 text-[22px] font-medium leading-[1.32] text-ink">
          How Flowgrid is built
        </h3>
        <dl className="mt-6 grid gap-8 sm:grid-cols-3">
          {FIGURES.map((figure) => (
            <div key={figure.value}>
              <dd className="text-[44px] font-light leading-none tracking-[-0.5px] text-ink tabular-nums">
                {figure.value}
              </dd>
              <dt className="mt-2 max-w-[36ch] text-[14px] leading-[1.5] text-slate">
                {figure.label}
              </dt>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

export function InChargeBand() {
  return (
    <section aria-labelledby="in-charge" className="border-b border-bone bg-band">
      <div className="mx-auto grid w-full max-w-[1200px] gap-10 px-6 py-16 lg:grid-cols-[6fr_5fr]">
        <div>
          <Kicker>You stay in charge</Kicker>
          <h2 id="in-charge" className={bandTitle}>
            Flowgrid drafts and proposes. A person decides.
          </h2>
          <p className="mt-6 max-w-2xl text-[18px] leading-[1.42] text-slate">
            Every change Flowgrid suggests waits for a person to accept it,
            and every acceptance and rejection is recorded. The rule is built
            into the system itself, not just the screen, so nothing reaches a
            funder, a client or a partner without someone clicking to send it.
          </p>
        </div>
        <DotList items={IN_CHARGE} tone="trust" className="flex flex-col gap-6 lg:pt-10" />
      </div>
    </section>
  );
}

export function AudiencesSection() {
  return (
    <Section kicker="Who it’s for" title="Made for small UK organisations, whatever you do">
      <p className="-mt-4 mb-10 max-w-2xl text-[18px] leading-[1.42] text-slate">
        Flowgrid suits teams of 3 to 50 people who write the same kinds of
        documents again and again and need to show where their facts came
        from.
      </p>
      <div className="grid gap-6 md:grid-cols-2">
        {AUDIENCES.map((card) => (
          <div key={card.title} className="flex flex-col rounded-lg border border-bone p-6">
            <h3 className="text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink">
              {card.title}
            </h3>
            <DotList items={card.points} className="mt-4 flex flex-1 flex-col gap-3" />
            <Link href={card.link.href} className={`${ctaOutline} mt-6 self-start`}>
              {card.link.label}
            </Link>
          </div>
        ))}
      </div>
    </Section>
  );
}

export function CostsSection() {
  return (
    <Section kicker="Costs" title="Know what it’s doing and what it costs">
      <div className="grid gap-10 lg:grid-cols-[5fr_7fr]">
        <p className="max-w-xl text-[18px] leading-[1.42] text-slate">
          You can see what Flowgrid is doing and what it costs, answer by
          answer and month by month.
        </p>
        <DotList items={COSTS} className="flex flex-col gap-5" />
      </div>
    </Section>
  );
}

export function TrustBand() {
  return (
    <section aria-labelledby="trust" className="border-y border-bone bg-band">
      <div className="mx-auto w-full max-w-[1200px] px-6 py-16">
        <Kicker>Trust &amp; controls</Kicker>
        <h2 id="trust" className={bandTitle}>
          Built so you can check its work
        </h2>
        <DotList
          items={TRUST}
          tone="trust"
          className="mt-10 grid gap-x-10 gap-y-6 md:grid-cols-2"
        />
        <Link href="/security-and-data" className={`${ctaGhost} mt-8`}>
          Read the security &amp; data detail
        </Link>
      </div>
    </section>
  );
}
