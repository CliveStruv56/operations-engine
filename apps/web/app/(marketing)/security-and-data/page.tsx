import type { Metadata } from "next";
import Link from "next/link";
import { ctaGhost, DemoCta, Kicker, Section } from "../ui";

export const metadata: Metadata = {
  title: "Security & data",
  description:
    "How Flowgrid handles your data in plain English: single-tenant isolation enforced in the database, gated model access, per-call cost telemetry and cited answers.",
  alternates: { canonical: "/security-and-data" },
};

const SECTIONS = [
  {
    kicker: "Isolation",
    title: "Can another customer see our data?",
    plain:
      "No. Each customer's workspace is a separate tenant, and separation is enforced inside the database itself — not just by application code.",
    detail:
      "Every tenant-scoped table is protected by Postgres row-level security. Every query runs inside a tenant context, and a cross-tenant isolation test suite blocks releases in CI if any table is reachable across tenants.",
  },
  {
    kicker: "AI providers",
    title: "Where do our documents go when the AI answers?",
    plain:
      "Model requests go through a single gateway to vetted cloud providers, with zero-data-retention hosting in Western jurisdictions as the default. Your documents are not used to train anyone's models.",
    detail:
      "All model access runs through one LiteLLM gateway — application code never talks to a provider directly, so the provider list stays small, auditable and swappable. Provider terms are documented per deployment; commercial guarantees always match the signed terms, not this page.",
  },
  {
    kicker: "Accuracy",
    title: "Will it invent facts?",
    plain:
      "Grounded answers cite the document and page they came from, so you can check any claim in one click. When the vault has no answer, Flowgrid says so rather than improvising.",
    detail:
      "Retrieval runs over your own vault; answers carry source excerpts, and drafting workflows are transcribe → verify → draft → paste, with a human review step before anything leaves the workspace. Flowgrid never submits documents to a funder or client on your behalf.",
  },
  {
    kicker: "Cost & oversight",
    title: "What is the AI doing, and what does it cost?",
    plain:
      "Every AI call is recorded with its usage and cost, visible in the workspace. There is no unmetered background AI activity.",
    detail:
      "Cost telemetry is captured per call at the gateway. Roles and per-module entitlements control who can use which capability, and workspaces are provisioned by the platform operator — there is no open signup.",
  },
  {
    kicker: "Your data, your exit",
    title: "What if we leave?",
    plain:
      "Your documents and records are yours. Exports are standard formats — PDF, PowerPoint, CSV — and we will agree return and deletion of your data as part of your terms.",
    detail:
      "Retention and deletion commitments are set out in your agreement. Ask us anything specific before you sign — we would rather answer it now.",
  },
];

export default function SecurityPage() {
  return (
    <>
      <section className="mx-auto w-full max-w-[1200px] px-6 pb-4 pt-14 lg:pt-20">
        <Kicker>Security &amp; data</Kicker>
        <h1 className="mt-4 max-w-4xl text-[40px] font-light leading-[1.15] tracking-[-0.92px] text-ink md:text-[56px]">
          The questions you should ask any AI vendor — answered plainly.
        </h1>
        <p className="mt-6 max-w-2xl text-[18px] leading-[1.42] tracking-[-0.14px] text-slate">
          No badges, no absolutes — just how the system actually works. Each
          answer has a plain-English version and the technical detail behind
          it.
        </p>
      </section>

      <Section>
        <div className="flex flex-col gap-6">
          {SECTIONS.map((s) => (
            <div key={s.kicker} className="rounded-lg border border-bone p-6 md:p-8">
              <Kicker>{s.kicker}</Kicker>
              <h2 className="mt-3 text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink">
                {s.title}
              </h2>
              <p className="mt-3 max-w-3xl text-[18px] leading-[1.42] text-ink">
                {s.plain}
              </p>
              <p className="mt-4 max-w-3xl border-t border-bone pt-4 text-[15px] leading-[1.55] text-slate">
                <span className="font-medium uppercase tracking-[0.08em] text-[12px] text-slate">
                  Technical detail ·{" "}
                </span>
                {s.detail}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <Section kicker="Anything else?" title="Ask us the awkward question">
        <p className="max-w-2xl text-[18px] leading-[1.42] text-slate">
          Due diligence questions are welcome — data flow diagrams,
          subprocessor lists, retention specifics. If we can&rsquo;t
          substantiate an answer, we&rsquo;ll tell you that too.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-5">
          <DemoCta label="Ask a question" />
          <Link href="/privacy" className={ctaGhost}>
            Read the privacy notice
          </Link>
        </div>
      </Section>
    </>
  );
}
