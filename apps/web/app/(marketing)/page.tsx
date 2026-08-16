import type { Metadata } from "next";
import Link from "next/link";
import { HeroVisual } from "./hero-visual";
import { PilotForm } from "./pilot-form";
import { ctaGhost, ctaOutline, DemoCta, Kicker, Section, StatusCard } from "./ui";

export const metadata: Metadata = {
  title: "Flowgrid OS — Turn what your organisation knows into work you can trust",
  description:
    "Cited answers from your own documents, confirmed organisational facts and live projects in one workspace. Built for UK small organisations and specialist teams.",
  alternates: { canonical: "/" },
};

const BEFORE_AFTER = [
  {
    before: "Scattered documents",
    after: "Cited answers with a visible source",
  },
  {
    before: "Repeated re-keying",
    after: "Reusable, reviewed organisational facts",
  },
  {
    before: "Blank-page reporting",
    after: "Structured outputs assembled from live records",
  },
];

const STEPS = [
  {
    label: "Step 1 · The evidence",
    title: "Bring the evidence together",
    body: "Add documents and connect the facts your organisation relies on. Everything stays inside your own workspace, ready to be found again.",
  },
  {
    label: "Step 2 · The structure",
    title: "Keep work structured",
    body: "Use projects, plans and specialist registers instead of rebuilding context in every chat. The workspace remembers, so your team doesn't have to.",
  },
  {
    label: "Step 3 · The output",
    title: "Produce and review",
    body: "Draft from evidence, check every citation against its source, and export a deliverable your client or funder can actually use.",
  },
];

const PROOF = [
  {
    title: "Ask the vault; open the cited page",
    body: "Answers link back to the exact document and page they came from — and say plainly when the vault has nothing.",
  },
  {
    title: "Confirm a claim once; reuse it everywhere",
    body: "Charity numbers, policies, insurance dates: review a fact once and every draft draws on the confirmed version.",
  },
  {
    title: "Turn a project into a plan with owned tasks",
    body: "Projects carry stages, budgets and risks, so plans come from live records rather than a blank page.",
  },
  {
    title: "Export finished, branded outputs",
    body: "A conversation becomes a PDF; a funder response becomes editable PowerPoint — in your organisation's own branding.",
  },
];

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <section className="mx-auto grid w-full max-w-[1200px] gap-12 px-6 pb-16 pt-14 lg:grid-cols-[7fr_6fr] lg:items-center lg:pt-20">
        <div>
          <h1 className="text-[44px] font-light leading-[1.1] tracking-[-0.92px] text-ink md:text-[69px] md:tracking-[-1.45px]">
            Turn what your organisation knows into work you can trust.
          </h1>
          <p className="mt-6 max-w-xl text-[18px] leading-[1.42] tracking-[-0.14px] text-slate">
            Flowgrid connects your source documents, confirmed facts and live
            projects in one workspace — so your team can find cited answers,
            run repeatable workflows and produce finished, branded outputs.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            <DemoCta />
            <Link href="/platform" className={ctaGhost}>
              Explore the platform
            </Link>
          </div>
          <p className="mt-8 text-[13px] font-medium uppercase tracking-[0.08em] text-faint">
            Built for UK small organisations and specialist teams
          </p>
        </div>
        <HeroVisual />
      </section>

      {/* Problem → outcome strip */}
      <section aria-label="Before and after" className="border-y border-bone bg-band">
        <div className="mx-auto grid w-full max-w-[1200px] gap-8 px-6 py-12 md:grid-cols-3">
          {BEFORE_AFTER.map((pair) => (
            <div key={pair.before}>
              <p className="text-[14px] text-faint line-through decoration-1">
                {pair.before}
              </p>
              <p className="mt-1.5 text-[18px] leading-[1.42] text-ink">
                {pair.after}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <Section kicker="How it works" title="One workspace, from evidence to deliverable">
        <ol className="grid gap-6 md:grid-cols-3">
          {STEPS.map((step) => (
            <li key={step.label} className="rounded-lg border border-bone p-6">
              <Kicker>{step.label}</Kicker>
              <h3 className="mt-3 text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink">
                {step.title}
              </h3>
              <p className="mt-3 text-[16px] leading-[1.45] text-slate">
                {step.body}
              </p>
            </li>
          ))}
        </ol>
      </Section>

      {/* Product proof */}
      <Section kicker="Proof" title="What that looks like on a normal working day">
        <div className="grid gap-6 md:grid-cols-2">
          {PROOF.map((item) => (
            <div key={item.title} className="rounded-lg border border-bone p-6">
              <h3 className="text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink">
                {item.title}
              </h3>
              <p className="mt-3 text-[16px] leading-[1.45] text-slate">
                {item.body}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* Solutions */}
      <Section kicker="Solutions" title="Start from your workflow, not a blank tool">
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="flex flex-col">
            <StatusCard
              tone="active"
              label="Active · Piloting now"
              title="Groundwork — community-led development"
              tags={["Stage gates", "Funding", "Client reporting"]}
            />
            <p className="mt-4 flex-1 text-[16px] leading-[1.45] text-slate">
              Keep community-led development projects moving through stage
              gates, funding, budget, risks and client reporting.
            </p>
            <Link href="/solutions/groundwork" className={`${ctaOutline} mt-4 self-start`}>
              Explore Groundwork
            </Link>
          </div>
          <div className="flex flex-col">
            <StatusCard
              tone="active"
              label="Active · Piloting now"
              title="Grantwork — applications to monitoring"
              tags={["Applications", "Conditions", "Impact evidence"]}
            />
            <p className="mt-4 flex-1 text-[16px] leading-[1.45] text-slate">
              Manage applications, award conditions, impact evidence and
              monitoring returns in one workflow.
            </p>
            <Link href="/solutions/grantwork" className={`${ctaOutline} mt-4 self-start`}>
              Explore Grantwork
            </Link>
          </div>
          <div className="flex flex-col">
            <StatusCard
              tone="neutral"
              label="Core · Always included"
              title="Core platform — vault, claims and projects"
              tags={["Cited answers", "Claims", "Exports"]}
            />
            <p className="mt-4 flex-1 text-[16px] leading-[1.45] text-slate">
              For teams that need cited knowledge, controlled facts and
              repeatable project work without a sector module.
            </p>
            <Link href="/platform" className={`${ctaOutline} mt-4 self-start`}>
              Explore the platform
            </Link>
          </div>
        </div>
      </Section>

      {/* Trust and controls */}
      <section className="border-y border-bone bg-band">
        <div className="mx-auto w-full max-w-[1200px] px-6 py-16">
          <Kicker>Trust &amp; controls</Kicker>
          <h2 className="mt-3 max-w-3xl text-[29px] font-normal leading-[1.3] tracking-[-0.32px] text-ink md:text-[40px] md:leading-[1.22] md:tracking-[-0.48px]">
            Built so you can check its work
          </h2>
          <ul className="mt-10 grid gap-x-10 gap-y-6 md:grid-cols-2">
            {[
              "Every tenant-scoped data table is protected by database row-level security — isolation is enforced in the database, not just the app.",
              "Roles and per-module entitlements limit what each user can see and do.",
              "AI usage and cost are recorded on every call, so you always know what the assistant is spending.",
              "Grounded answers link back to the document and page they came from — and say so when they can't.",
            ].map((line) => (
              <li key={line} className="flex gap-3 text-[16px] leading-[1.45] text-slate">
                <span aria-hidden className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-grounded" />
                {line}
              </li>
            ))}
          </ul>
          <Link href="/security-and-data" className={`${ctaGhost} mt-8`}>
            Read the security &amp; data detail
          </Link>
        </div>
      </section>

      {/* Final CTA */}
      <Section kicker="Next step" title="Bring one repeated workflow. We'll show you how it fits.">
        <div className="max-w-2xl">
          <p className="text-[18px] leading-[1.42] text-slate">
            A 20-minute demo around a report, bid or return you already
            produce — or join the pilot list and we&rsquo;ll be in touch when
            a place opens.
          </p>
          <div className="mt-8">
            <DemoCta label="Book a 20-minute demo" />
          </div>
          <div className="mt-10 border-t border-bone pt-8">
            <PilotForm />
          </div>
        </div>
      </Section>
    </>
  );
}
