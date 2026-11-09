import type { Metadata } from "next";
import { SolutionPage, type SolutionContent } from "../solution-page";

export const metadata: Metadata = {
  title: "Grantwork — grant applications and reporting",
  description:
    "Manage grant applications, award conditions, impact evidence and monitoring returns in one workflow — carrying evidence from application to return.",
  alternates: { canonical: "/solutions/grantwork" },
};

const content: SolutionContent = {
  kicker: "Grantwork · Grant funding · For grant-funded organisations",
  headline: "Carry evidence from application to monitoring return.",
  workaround:
    "The facts a funder asks for at application time are the same ones they ask for at monitoring time — but most teams reconstruct them twice, in different Word documents, months apart. Grantwork, the grant-funding module of Flowgrid OS, keeps funders, conditions and evidence in one record so nothing is written from scratch twice.",
  diagram: {
    ariaLabel:
      "Your documents and confirmed organisational facts flow into one record per grant, carrying its stages, conditions, deadlines and impact evidence. Application drafts, monitoring returns and paste-ready funder-form answers are drafted out of that record, and every citation shows its source. Nothing goes to a funder without your say-so.",
    vault: {
      caption: "past bids · policies · accounts",
      arrowLabel: "source document named",
    },
    facts: {
      caption: "charity no. · safeguarding",
      arrowLabel: "reused in every bid",
    },
    record: {
      title: "One record per grant",
      gatesDone: 2,
      gatesTotal: 5,
      spineLabel: "stages & conditions",
      chips: ["conditions", "deadlines", "impact"],
      footnote: "evidence accumulates all year",
    },
    outputs: [
      { label: "Application draft" },
      { label: "Monitoring return" },
      { label: "Funder-form answers", violet: true },
    ],
    outLabel: "drafted from the record",
    returnLabel:
      "every citation shows its source — nothing goes to a funder without your say-so",
  },
  outcomes: [
    {
      title: "Applications answered from confirmed facts",
      body: "Charity numbers, policies, safeguarding statements and track record come from your confirmed organisational facts — consistent in every application.",
      evidence:
        "Funder-form transcription and drafting that pulls from confirmed facts and your documents, with citations to check.",
      spot: "claim",
    },
    {
      title: "Award conditions stop being surprises",
      body: "Conditions and reporting deadlines are recorded against each award the day it lands, not rediscovered in a panic before a return is due.",
      evidence:
        "Per-grant stages and conditions visible across the whole portfolio.",
      spot: "calendar",
    },
    {
      title: "Monitoring returns from live impact evidence",
      body: "Outcomes and impact measures accumulate against the grant through the year, so the return is assembled from records rather than memory.",
      evidence:
        "Impact measures per grant, drawn into monitoring drafts for you to review. Nothing goes to a funder without your say-so.",
      spot: "impact",
    },
  ],
  workspace: [
    "A register of funders, applications and live awards",
    "Grant applications as a tab on any project — including a development scheme",
    "Stages, conditions and deadlines per grant",
    "Impact measures and outcome evidence collected against each award",
    "Your documents: previous bids, policies, accounts and reports, all citable",
    "Confirmed organisational facts reused across every application",
  ],
  deliverables: [
    "Application draft",
    "Monitoring return draft",
    "Funder-form answers (paste-ready)",
    "Impact card (PDF summary)",
  ],
  vignette: "reporting-calendar",
  trust:
    "Application drafts and monitoring returns are Word downloads, marked as drafts for review. Funder-form answers are text you paste into the funder's own portal. Flowgrid never submits to a funder, and your data is isolated from every other customer's at the database level.",
  fit: [
    "You hold or apply for several grants a year with written reporting attached.",
    "Different funders keep asking for the same organisational facts.",
    "You want drafts grounded in your own documents, not generic AI text.",
  ],
  notFit: [
    "You want automatic submission to funder portals — Flowgrid deliberately never submits on your behalf.",
    "You need a funder-discovery database; Grantwork manages the grants you pursue, it doesn't find them.",
    "A single annual grant with a one-page return may not repay the setup.",
  ],
  ctaHeading:
    "Bring your next application or return. We'll pilot it end to end.",
};

export default function GrantworkPage() {
  return <SolutionPage content={content} />;
}
