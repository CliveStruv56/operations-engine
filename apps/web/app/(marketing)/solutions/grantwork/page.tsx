import type { Metadata } from "next";
import { SolutionPage, type SolutionContent } from "../solution-page";

export const metadata: Metadata = {
  title: "Grantwork — grant applications and reporting",
  description:
    "Manage grant applications, award conditions, impact evidence and monitoring returns in one workflow — carrying evidence from application to return.",
  alternates: { canonical: "/solutions/grantwork" },
};

const content: SolutionContent = {
  kicker: "Grantwork · For grant-funded organisations",
  headline: "Carry evidence from application to monitoring return.",
  workaround:
    "The facts a funder asks for at application time are the same ones they ask for at monitoring time — but most teams reconstruct them twice, in different Word documents, months apart. Grantwork keeps funders, conditions and evidence in one record so nothing is written from scratch twice.",
  diagram: {
    ariaLabel:
      "Documents from the vault and confirmed organisational facts flow into one record per grant, carrying its stages, conditions, deadlines and impact evidence. Application drafts, monitoring returns, paste-ready funder-form answers and editable PowerPoint are assembled out of that record, and every answer cites its evidence — you verify and paste; Flowgrid never submits to a funder.",
    vault: {
      caption: "past bids · policies · accounts",
      arrowLabel: "cited by page",
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
      { label: "Editable PowerPoint" },
      { label: "Funder-form answers", violet: true },
    ],
    outLabel: "assembled from the record",
    returnLabel:
      "every answer cites its evidence — you verify and paste; Flowgrid never submits",
  },
  outcomes: [
    {
      title: "Applications answered from confirmed facts",
      body: "Charity numbers, policies, safeguarding statements and track record come from your reviewed claims register — consistent in every application.",
      evidence:
        "Funder-form transcription and drafting that pulls from claims and the vault, with citations to check.",
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
        "Impact measures per grant, drawn into monitoring drafts you review before anything leaves the building.",
      spot: "impact",
    },
  ],
  workspace: [
    "A register of funders, applications and live awards",
    "Stages, conditions and deadlines per grant",
    "Impact measures and outcome evidence collected against each award",
    "The document vault: previous bids, policies, accounts and reports, all citable",
    "Confirmed organisational facts reused across every application",
  ],
  deliverables: [
    "Application draft",
    "Monitoring return draft",
    "Funder-form answers (paste-ready)",
    "Editable PowerPoint",
    "PDF report",
  ],
  trust:
    "Drafting is transcribe, verify, draft, paste: Flowgrid drafts from cited evidence, you verify and paste into the funder's own portal. Flowgrid never submits to a funder, and your data is isolated from every other customer's at the database level.",
  fit: [
    "You hold or apply for several grants a year with written reporting attached.",
    "Different funders keep asking for the same organisational facts.",
    "You want drafts grounded in your own documents, not generic AI text.",
  ],
  notFit: [
    "You want automatic submission to funder portals — Flowgrid deliberately stops at a verified draft.",
    "You need a funder-discovery database; Grantwork manages the grants you pursue, it doesn't find them.",
    "A single annual grant with a one-page return may not repay the setup.",
  ],
  ctaHeading:
    "Bring your next application or return. We'll pilot it end to end.",
};

export default function GrantworkPage() {
  return <SolutionPage content={content} />;
}
