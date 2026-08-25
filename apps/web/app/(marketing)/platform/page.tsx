import type { Metadata } from "next";
import Link from "next/link";
import { ctaGhost, DemoCta, Kicker, Section, TagPill } from "../ui";
import { ClaimsRegisterVignette } from "../vignettes";

export const metadata: Metadata = {
  title: "Platform — vault, claims, projects and outputs",
  description:
    "The Flowgrid core platform: a cited knowledge vault, a claims register of confirmed facts, structured projects and finished branded outputs — with governance built in.",
  alternates: { canonical: "/platform" },
};

const PILLARS = [
  {
    kicker: "The vault",
    title: "Knowledge that shows its sources",
    body: "Upload the documents your organisation runs on — policies, minutes, bids, accounts, surveys. Ask in plain English and get an answer with a citation that opens the exact page it came from. When the vault has nothing, Flowgrid says so instead of guessing.",
    tags: ["Cited answers", "Page-level sources", "Honest 'not found'"],
  },
  {
    kicker: "The claims register",
    title: "One true place for what you assert about yourselves",
    body: "Charity number, insurance dates, safeguarding policy version, headline outcomes: facts your team re-keys constantly. Review each one once, and every draft across the workspace reuses the confirmed version — so documents stop disagreeing with each other.",
    tags: ["Reviewed once", "Reused everywhere", "Visible status"],
  },
  {
    kicker: "Projects",
    title: "Structured work, not disposable chats",
    body: "Projects hold plans, tasks with owners, and the records your modules add — stage gates, budgets, risks, grant conditions. Context lives with the work, so nobody rebuilds it in a new conversation every Monday.",
    tags: ["Plans & owned tasks", "Live records", "Module registers"],
  },
  {
    kicker: "Outputs",
    title: "Finished deliverables, in your branding",
    body: "Turn a conversation into a PDF, a funder response into editable PowerPoint, a project into a client-ready health card. Outputs are assembled from live records and cited evidence — then you review before anything leaves the building.",
    tags: ["PDF export", "Editable PowerPoint", "Branded documents"],
  },
];

const GOVERNANCE = [
  "Your workspace is a single tenant, isolated from every other customer at the database level by row-level security.",
  "Roles and per-module entitlements control what each user can see and do.",
  "Every AI call is metered: model, usage and cost are recorded so spend is never a mystery.",
  "Model access runs through one gateway to vetted providers — with zero-data-retention hosting as the default.",
];

export default function PlatformPage() {
  return (
    <>
      <section className="mx-auto grid w-full max-w-[1200px] gap-12 px-6 pb-4 pt-14 lg:grid-cols-[7fr_6fr] lg:items-center lg:pt-20">
        <div>
          <Kicker>Platform</Kicker>
          <h1 className="mt-4 max-w-4xl text-[40px] font-light leading-[1.15] tracking-[-0.92px] text-ink md:text-[56px]">
            A workspace built on evidence, not vibes.
          </h1>
          <p className="mt-6 max-w-2xl text-[18px] leading-[1.42] tracking-[-0.14px] text-slate">
            Four pieces work together: a vault of cited knowledge, a register of
            confirmed facts, structured projects and finished outputs. Each one
            makes the others more useful — that&rsquo;s the point of a platform
            rather than a pile of tools.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            <DemoCta />
            <Link href="/security-and-data" className={ctaGhost}>
              Security &amp; data detail
            </Link>
          </div>
        </div>
        <ClaimsRegisterVignette />
      </section>

      <Section>
        <div className="grid gap-6 md:grid-cols-2">
          {PILLARS.map((p) => (
            <div key={p.kicker} className="rounded-lg border border-bone p-6 md:p-8">
              <Kicker>{p.kicker}</Kicker>
              <h2 className="mt-3 text-[22px] font-medium leading-[1.32] tracking-[-0.22px] text-ink">
                {p.title}
              </h2>
              <p className="mt-3 text-[16px] leading-[1.45] text-slate">{p.body}</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {p.tags.map((t) => (
                  <TagPill key={t}>{t}</TagPill>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      <section className="border-y border-bone bg-band">
        <div className="mx-auto w-full max-w-[1200px] px-6 py-16">
          <Kicker>Governance</Kicker>
          <h2 className="mt-3 max-w-3xl text-[29px] font-normal leading-[1.3] tracking-[-0.32px] text-ink md:text-[40px] md:leading-[1.22] md:tracking-[-0.48px]">
            Controls that hold up to a hard question
          </h2>
          <ul className="mt-10 grid gap-x-10 gap-y-6 md:grid-cols-2">
            {GOVERNANCE.map((line) => (
              <li key={line} className="flex gap-3 text-[16px] leading-[1.45] text-slate">
                <span aria-hidden className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-grounded" />
                {line}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <Section
        kicker="Modules"
        title="Sector workflows switch on per workspace"
      >
        <p className="max-w-2xl text-[18px] leading-[1.42] text-slate">
          The core platform carries every workspace. Sector modules —{" "}
          <Link href="/solutions/groundwork" className="text-deep-violet underline underline-offset-4">
            Groundwork
          </Link>{" "}
          for community-led development and{" "}
          <Link href="/solutions/grantwork" className="text-deep-violet underline underline-offset-4">
            Grantwork
          </Link>{" "}
          for grant-funded organisations — add specialist registers and
          deliverables on top, enabled per workspace so your team only sees
          what it uses.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-5">
          <DemoCta label="Book a 20-minute demo" />
          <Link href="/contact" className={ctaGhost}>
            Ask a question
          </Link>
        </div>
      </Section>
    </>
  );
}
