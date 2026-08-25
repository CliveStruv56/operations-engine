import Link from "next/link";
import { Spot, type SpotName } from "../spot-icons";
import { ctaGhost, DemoCta, Kicker, Section, TagPill } from "../ui";
import { WorkflowDiagram, type WorkflowDiagramContent } from "../workflow-diagram";

/* Shared decision-path template for solution pages (PRD §6). Content is a
 * typed object so availability and claims stay in one reviewable place. */

export interface SolutionContent {
  kicker: string;
  headline: string;
  workaround: string;
  diagram: WorkflowDiagramContent;
  outcomes: { title: string; body: string; evidence: string; spot: SpotName }[];
  workspace: string[];
  deliverables: string[];
  trust: string;
  fit: string[];
  notFit: string[];
  ctaHeading: string;
}

export function SolutionPage({ content }: { content: SolutionContent }) {
  return (
    <>
      {/* Headline + costly workaround */}
      <section className="mx-auto w-full max-w-[1200px] px-6 pb-4 pt-14 lg:pt-20">
        <Kicker>{content.kicker}</Kicker>
        <h1 className="mt-4 max-w-4xl text-[40px] font-light leading-[1.15] tracking-[-0.92px] text-ink md:text-[56px]">
          {content.headline}
        </h1>
        <p className="mt-6 max-w-2xl text-[18px] leading-[1.42] tracking-[-0.14px] text-slate">
          {content.workaround}
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-5">
          <DemoCta label="Discuss a pilot" />
          <Link href="/platform" className={ctaGhost}>
            See the core platform
          </Link>
        </div>
      </section>

      {/* End-to-end workflow */}
      <Section kicker="The workflow" title="One record, end to end">
        <WorkflowDiagram content={content.diagram} />
      </Section>

      {/* Outcomes */}
      <Section kicker="What changes" title="Three things that stop being painful">
        <div className="grid gap-6 lg:grid-cols-3">
          {content.outcomes.map((o, i) => (
            <div key={o.title} className="rounded-lg border border-bone p-6">
              <Spot name={o.spot} className="mb-4 h-auto w-full max-w-[220px]" />
              <Kicker>{`Outcome ${i + 1}`}</Kicker>
              <h3 className="mt-3 text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink">
                {o.title}
              </h3>
              <p className="mt-3 text-[16px] leading-[1.45] text-slate">{o.body}</p>
              <p className="mt-4 border-t border-bone pt-4 text-[14px] leading-[1.5] text-slate">
                <span className="font-medium text-ink">In the product: </span>
                {o.evidence}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* Workspace + deliverables */}
      <section className="border-y border-bone bg-band">
        <div className="mx-auto grid w-full max-w-[1200px] gap-12 px-6 py-16 lg:grid-cols-2">
          <div>
            <Kicker>In the workspace</Kicker>
            <h2 className="mt-3 text-[29px] font-normal leading-[1.3] tracking-[-0.32px] text-ink">
              What lives here
            </h2>
            <ul className="mt-6 flex flex-col gap-3">
              {content.workspace.map((item) => (
                <li key={item} className="flex gap-3 text-[16px] leading-[1.45] text-slate">
                  <span aria-hidden className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-deep-violet" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <Kicker>Deliverables</Kicker>
            <h2 className="mt-3 text-[29px] font-normal leading-[1.3] tracking-[-0.32px] text-ink">
              What comes out
            </h2>
            <div className="mt-6 flex flex-wrap gap-2.5">
              {content.deliverables.map((d) => (
                <TagPill key={d}>{d}</TagPill>
              ))}
            </div>
            <p className="mt-8 rounded-lg border border-bone bg-canvas p-5 text-[15px] leading-[1.5] text-slate">
              {content.trust}
            </p>
          </div>
        </div>
      </section>

      {/* Fit / not fit */}
      <Section kicker="Is this for you?" title="A good fit — and an honest miss">
        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-stone bg-pale-sage p-6">
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
              Likely a good fit
            </p>
            <ul className="mt-4 flex flex-col gap-3">
              {content.fit.map((f) => (
                <li key={f} className="text-[16px] leading-[1.45] text-ink">
                  {f}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-bone p-6">
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
              Probably not yet
            </p>
            <ul className="mt-4 flex flex-col gap-3">
              {content.notFit.map((f) => (
                <li key={f} className="text-[16px] leading-[1.45] text-slate">
                  {f}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      {/* Pilot CTA */}
      <Section kicker="Next step" title={content.ctaHeading}>
        <div className="flex flex-wrap items-center gap-5">
          <DemoCta label="Discuss a pilot" />
          <Link href="/contact" className={ctaGhost}>
            Ask a question first
          </Link>
        </div>
      </Section>
    </>
  );
}
