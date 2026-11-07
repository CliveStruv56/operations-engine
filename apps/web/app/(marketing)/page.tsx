import type { Metadata } from "next";
import Link from "next/link";
import { DemoAgendaPanel } from "./cta-panels";
import { HeroVisual } from "./hero-visual";
import { PilotForm } from "./pilot-form";
import { BEFORE_AFTER, STEPS, WORKSPACE_DIAGRAM } from "./home-content";
import {
  AudiencesSection,
  CapabilitiesBand,
  CostsSection,
  InChargeBand,
  TrustBand,
} from "./home-sections";
import { Spot } from "./spot-icons";
import { ctaGhost, ctaOutline, DemoCta, Kicker, Section, StatusCard } from "./ui";
import { WorkflowDiagram } from "./workflow-diagram";
import { PRODUCT_LANGUAGE } from "@/lib/product-language";

export const metadata: Metadata = {
  title: "Flowgrid OS — Turn what your organisation knows into work you can trust",
  description:
    "Answers from your own documents that show where they came from, facts you confirm once, and first drafts of the reports and bids you write every month.",
  alternates: { canonical: "/" },
};

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
            Flowgrid is one workspace for your team&rsquo;s documents, confirmed
            facts and projects. It answers questions from your own documents
            and shows where each answer came from, drafts the reports, bids and
            monitoring returns you write again and again, and takes on routine
            jobs. Nothing changes and nothing goes to a funder, client or
            partner until a person says yes.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            <DemoCta />
            <Link href="/platform" className={ctaGhost}>
              See how Flowgrid works
            </Link>
          </div>
          <p className="mt-8 text-[13px] font-medium uppercase tracking-[0.08em] text-slate">
            For small UK organisations of 3 to 50 people
          </p>
          <p className="mt-2 max-w-xl text-[14px] leading-[1.5] text-slate">
            Charities and community groups, development trusts, professional
            firms and small businesses: anyone who writes the same kinds of
            reports, bids and monitoring returns every month and needs to show
            where the facts came from.
          </p>
        </div>
        <HeroVisual />
      </section>

      {/* Problem → outcome strip */}
      <section aria-label="Before and after" className="border-y border-bone bg-band">
        <div className="mx-auto grid w-full max-w-[1200px] gap-8 px-6 py-12 md:grid-cols-2 lg:grid-cols-4">
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

      <CapabilitiesBand />

      <InChargeBand />

      <AudiencesSection />

      {/* Mid-page call to action */}
      <div className="flex justify-center px-6 pb-16">
        <DemoCta />
      </div>

      {/* How it works */}
      <Section kicker="How it works" title="From first sign-in to a first useful draft">
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
        <p className="mt-8 max-w-3xl text-[16px] leading-[1.45] text-slate">
          Want to look around first? Ask us for a sample workspace when you
          book a demo. It&rsquo;s a fictional development trust with documents,
          a project and a grant already in place, open for a limited time, so
          your team can try Flowgrid before adding anything of its own.
        </p>
        <div className="mt-12">
          <WorkflowDiagram content={WORKSPACE_DIAGRAM} />
        </div>
      </Section>

      {/* Solutions */}
      <Section kicker="Solutions" title="Start from your workflow, not a blank tool">
        <p className="mb-10 max-w-2xl text-[18px] leading-[1.42] text-slate">
          {PRODUCT_LANGUAGE.core.everyProject} {PRODUCT_LANGUAGE.core.modulesAdd}
        </p>
        <p className="-mt-6 mb-10 max-w-2xl text-[16px] leading-[1.45] text-slate">
          In plain terms: each project has its own chat, its own documents and,
          if you want one, a task plan where each task can be given to a named
          person. A module adds what your sector needs, such as the five stages
          of a development project or your grant records.
        </p>
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="flex flex-col">
            <StatusCard
              tone="active"
              label={PRODUCT_LANGUAGE.groundwork.availability}
              title="Groundwork — community-led development"
              tags={["Stage gates", "Funding", "Client reporting"]}
            />
            <p className="mt-4 flex-1 text-[16px] leading-[1.45] text-slate">
              {PRODUCT_LANGUAGE.groundwork.combined}: keep community-led
              development projects moving through stage gates, funding, budget,
              risks and client reporting.
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
              {PRODUCT_LANGUAGE.grantwork.combined}: manage applications, award
              conditions, impact evidence and monitoring returns, as a tab on
              any project.
            </p>
            <Link href="/solutions/grantwork" className={`${ctaOutline} mt-4 self-start`}>
              Explore Grantwork
            </Link>
          </div>
          <div className="flex flex-col">
            <StatusCard
              tone="neutral"
              label="Core · Always included"
              title={`${PRODUCT_LANGUAGE.core.label} — ${PRODUCT_LANGUAGE.core.triplet}`}
              tags={["Answers with sources", "Confirmed facts", "Exports"]}
            />
            <p className="mt-4 flex-1 text-[16px] leading-[1.45] text-slate">
              For teams that need cited answers, confirmed facts and
              projects with chat, documents and an optional plan — without a sector
              module. Every workspace starts with ready-made playbooks for
              common jobs.
            </p>
            <Link href="/platform" className={`${ctaOutline} mt-4 self-start`}>
              Explore the platform
            </Link>
          </div>
        </div>
        <p className="mt-10 max-w-3xl border-t border-bone pt-8 text-[16px] leading-[1.45] text-slate">
          A Community profile module records the place you serve, its services,
          facilities and figures, and downloads it as a branded PDF.
        </p>
      </Section>

      <CostsSection />

      <TrustBand />

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
