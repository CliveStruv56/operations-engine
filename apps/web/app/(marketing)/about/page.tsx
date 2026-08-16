import type { Metadata } from "next";
import Link from "next/link";
import { ctaGhost, DemoCta, Kicker, Section } from "../ui";

export const metadata: Metadata = {
  title: "About",
  description:
    "Why Flowgrid OS exists: small UK organisations run on knowledge they can't reuse. Flowgrid turns that knowledge into cited, checkable, finished work.",
  alternates: { canonical: "/about" },
};

const BELIEFS = [
  {
    title: "Evidence beats eloquence",
    body: "An answer you can't trace is a liability. Everything Flowgrid produces links back to the document it came from, and it says plainly when it doesn't know.",
  },
  {
    title: "Small teams deserve real software",
    body: "Enterprise platforms ignore 12-person organisations; generic chatbots patronise them. Flowgrid is built to the standard of the former at the scale of the latter.",
  },
  {
    title: "The human stays in charge",
    body: "Flowgrid drafts, cites and assembles — people verify and send. Nothing leaves your workspace for a funder or client without a person deciding it should.",
  },
  {
    title: "One workspace, honestly scoped",
    body: "We would rather do a handful of workflows properly than gesture at a hundred. What's on this site is what works today; the roadmap stays in the roadmap.",
  },
];

export default function AboutPage() {
  return (
    <>
      <section className="mx-auto w-full max-w-[1200px] px-6 pb-4 pt-14 lg:pt-20">
        <Kicker>About</Kicker>
        <h1 className="mt-4 max-w-4xl text-[40px] font-light leading-[1.15] tracking-[-0.92px] text-ink md:text-[56px]">
          Small organisations run on knowledge. Most of it is locked in old
          documents.
        </h1>
        <div className="mt-6 max-w-2xl space-y-4 text-[18px] leading-[1.42] tracking-[-0.14px] text-slate">
          <p>
            Flowgrid started with a pattern we kept seeing in UK charities,
            community organisations and the consultancies that support them:
            the answer to almost every question already existed — in a bid
            written two years ago, in trustee minutes, in a policy nobody
            could find. The work wasn&rsquo;t creating knowledge. It was
            finding it, checking it and re-typing it, over and over.
          </p>
          <p>
            So we built the workspace we thought those teams deserved: one
            place where documents become citable answers, facts are confirmed
            once and reused everywhere, and reports assemble themselves from
            live records instead of a blank page.
          </p>
          <p>
            Flowgrid OS is built by a small, independent UK team, working
            closely with pilot organisations in community development and
            grant-funded work. We&rsquo;re deliberately unflashy about AI:
            it&rsquo;s the engine, not the point. The point is work you can
            stand behind.
          </p>
        </div>
      </section>

      <Section kicker="What we believe" title="Four principles the product is built on">
        <div className="grid gap-6 md:grid-cols-2">
          {BELIEFS.map((b) => (
            <div key={b.title} className="rounded-lg border border-bone p-6">
              <h2 className="text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink">
                {b.title}
              </h2>
              <p className="mt-3 text-[16px] leading-[1.45] text-slate">{b.body}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section kicker="Talk to us" title="We'd like to see the workflow that wastes your week">
        <div className="flex flex-wrap items-center gap-5">
          <DemoCta />
          <Link href="/solutions/groundwork" className={ctaGhost}>
            See what we&rsquo;re piloting
          </Link>
        </div>
      </Section>
    </>
  );
}
