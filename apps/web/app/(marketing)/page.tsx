import type { Metadata } from "next";
import Link from "next/link";
import { DemoAgendaPanel } from "./cta-panels";
import { HeroVisual } from "./hero-visual";
import { PilotForm } from "./pilot-form";
import { Spot, type SpotName } from "./spot-icons";
import { ctaGhost, ctaOutline, DemoCta, Kicker, Section, StatusCard } from "./ui";
import { WorkflowDiagram, type WorkflowDiagramContent } from "./workflow-diagram";
import { PRODUCT_LANGUAGE } from "@/lib/product-language";

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

const STEPS: { label: string; title: string; body: string; spot: SpotName }[] = [
  {
    label: "Step 1 · The evidence",
    title: "Bring the evidence together",
    body: "Add documents and connect the facts your organisation relies on. Everything stays inside your own workspace, ready to be found again.",
    spot: "evidence",
  },
  {
    label: "Step 2 · The structure",
    title: "Keep work structured",
    body: "Use projects, plans and specialist registers instead of rebuilding context in every chat. The workspace remembers, so your team doesn't have to.",
    spot: "structure",
  },
  {
    label: "Step 3 · The output",
    title: "Produce and review",
    body: "Draft from evidence, check every citation against its source, and export a deliverable your client or funder can actually use.",
    spot: "output",
  },
];

const WORKSPACE_DIAGRAM: WorkflowDiagramContent = {
  ariaLabel:
    "Documents from the vault and confirmed organisational facts flow into one structured workspace of projects, plans and registers. Cited answers, client reports, funding bids and branded exports are produced out of it, and every output cites its source for you to review before anything leaves.",
  vault: {
    caption: "policies · minutes · reports",
    arrowLabel: "cited by page",
  },
  facts: {
    caption: "reviewed once",
    arrowLabel: "reused in every draft",
  },
  record: {
    title: "One structured workspace",
    gatesDone: 3,
    gatesTotal: 5,
    spineLabel: "projects, plans & registers",
    chips: ["projects", "claims", "registers"],
    footnote: "the workspace remembers",
  },
  outputs: [
    { label: "Cited answer", violet: true },
    { label: "Client report" },
    { label: "Funding bid" },
    { label: "Branded PDF / slides" },
  ],
  outLabel: "produced and reviewed",
  returnLabel:
    "every output cites its source — you review before anything leaves",
};

const PROOF: { title: string; body: string; spot: SpotName }[] = [
  {
    title: "Ask the vault; open the cited page",
    body: "Answers link back to the exact document and page they came from — and say plainly when the vault has nothing.",
    spot: "citation",
  },
  {
    title: "Confirm a claim once; reuse it everywhere",
    body: "Charity numbers, policies, insurance dates: review a fact once and every draft draws on the confirmed version.",
    spot: "claim",
  },
  {
    title: "Turn a project into a plan with owned tasks",
    body: "Projects carry stages, budgets and risks, so plans come from live records rather than a blank page.",
    spot: "plan",
  },
  {
    title: "Export finished, branded outputs",
    body: "A conversation becomes a PDF; a funder response becomes editable PowerPoint — in your organisation's own branding.",
    spot: "export",
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
            Find cited answers, keep recurring work structured, and produce
            outputs ready for review.
            <span className="mt-2 block">
              Flowgrid connects your source documents, confirmed facts and live
              projects in one workspace.
            </span>
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            <DemoCta />
            <Link href="/platform" className={ctaGhost}>
              See how Flowgrid works
            </Link>
          </div>
          <p className="mt-8 text-[13px] font-medium uppercase tracking-[0.08em] text-slate">
            Built for UK small organisations and specialist teams
          </p>
          <p className="mt-2 max-w-xl text-[14px] leading-[1.5] text-slate">
            Best suited to small teams managing recurring bids, reporting,
            development projects and evidence-heavy organisational work.
          </p>
        </div>
        <HeroVisual />
      </section>

      {/* Problem → outcome strip */}
      <section aria-label="Before and after" className="border-y border-bone bg-band">
        <div className="mx-auto grid w-full max-w-[1200px] gap-8 px-6 py-12 md:grid-cols-3">
          {BEFORE_AFTER.map((pair) => (
            <div key={pair.before}>
              <p className="text-[14px] text-slate line-through decoration-1">
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
              <Spot name={step.spot} className="mb-4 h-auto w-full max-w-[220px]" />
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
        <div className="mt-12">
          <WorkflowDiagram content={WORKSPACE_DIAGRAM} />
        </div>
      </Section>

      {/* Product proof — the page's one warm band (amber wash, marketing-only:
          see workflow-diagram.tsx for why it isn't a globals.css token) */}
      <section className="border-y border-bone bg-[#f2e9dc]">
        <div className="mx-auto w-full max-w-[1200px] px-6 py-16">
          <Kicker>Proof</Kicker>
          <h2 className="mt-3 max-w-3xl text-[29px] font-normal leading-[1.3] tracking-[-0.32px] text-ink md:text-[40px] md:leading-[1.22] md:tracking-[-0.48px]">
            What that looks like on a normal working day
          </h2>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {PROOF.map((item) => (
              <div key={item.title} className="rounded-lg border border-bone bg-canvas p-6">
                <Spot name={item.spot} className="mb-4 h-auto w-full max-w-[220px]" />
                <h3 className="text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink">
                  {item.title}
                </h3>
                <p className="mt-3 text-[16px] leading-[1.45] text-slate">
                  {item.body}
                </p>
              </div>
            ))}
          </div>
          <h3 className="mt-12 border-t border-bone pt-10 text-[22px] font-medium leading-[1.32] text-ink">
            How Flowgrid is structured
          </h3>
          <dl className="mt-6 grid gap-8 sm:grid-cols-3">
            <div>
              <dd className="text-[44px] font-light leading-none tracking-[-0.5px] text-ink tabular-nums">
                ≈24
              </dd>
              <dt className="mt-2 max-w-[36ch] text-[14px] leading-[1.5] text-slate">
                facts imported from one charity number, each with its public
                source
              </dt>
            </div>
            <div>
              <dd className="text-[44px] font-light leading-none tracking-[-0.5px] text-ink tabular-nums">
                5
              </dd>
              <dt className="mt-2 max-w-[36ch] text-[14px] leading-[1.5] text-slate">
                stage gates carrying every development project from idea to
                delivery
              </dt>
            </div>
            <div>
              <dd className="text-[44px] font-light leading-none tracking-[-0.5px] text-ink tabular-nums">
                0
              </dd>
              <dt className="mt-2 max-w-[36ch] text-[14px] leading-[1.5] text-slate">
                documents Flowgrid sends on your behalf — you review and send
                everything
              </dt>
            </div>
          </dl>
        </div>
      </section>

      {/* Solutions */}
      <Section kicker="Solutions" title="Start from your workflow, not a blank tool">
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="flex flex-col">
            <StatusCard
              tone="active"
              label={PRODUCT_LANGUAGE.groundwork.availability}
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
              label={PRODUCT_LANGUAGE.grantwork.availability}
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
              "Customer workspaces are isolated at the database level using row-level security — not only by application code.",
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
        <div className="grid gap-12 lg:grid-cols-[7fr_5fr]">
          <div>
            <p className="max-w-2xl text-[18px] leading-[1.42] text-slate">
              A 20-minute demo around a report, bid or return you already
              produce — or join the pilot list and we&rsquo;ll be in touch when
              a place opens.
            </p>
            <div className="mt-8">
              <DemoCta label="Book a 20-minute demo" />
            </div>
            <div className="mt-10 border-t border-bone pt-8">
              <p className="mb-4 text-[15px] leading-[1.5] text-slate">
                Not ready to book? Join the pilot list for occasional
                availability updates.
              </p>
              <PilotForm />
            </div>
          </div>
          <div>
            <DemoAgendaPanel />
          </div>
        </div>
      </Section>
    </>
  );
}
