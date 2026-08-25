import type { Metadata } from "next";
import { SolutionPage, type SolutionContent } from "../solution-page";

export const metadata: Metadata = {
  title: "Groundwork — community-led development projects",
  description:
    "Keep community-led development projects moving through stage gates, funding, budget, risks and client reporting — with the project record always current.",
  alternates: { canonical: "/solutions/groundwork" },
};

const content: SolutionContent = {
  kicker: "Groundwork · For community-led development",
  headline: "Keep the project record current. Let the client report follow.",
  workaround:
    "Most development consultants rebuild the same picture every month: trawling emails for the latest budget, re-keying risks into Word, and writing funder updates from memory. Groundwork keeps one live record per project, so reporting becomes an export, not an evening.",
  diagram: {
    ariaLabel:
      "Documents from the vault and confirmed organisational facts flow into one live project record with five stage gates and budget, funding and risk registers. Monthly client reports, funding bids, feasibility studies and the health card are drafted out of that record, and every figure cites its source for you to review before anything is sent.",
    vault: {
      caption: "surveys · minutes · studies",
      arrowLabel: "cited by page",
    },
    facts: {
      caption: "charity no. · policies",
      arrowLabel: "reused in every draft",
    },
    record: {
      title: "One live project record",
      gatesDone: 3,
      gatesTotal: 5,
      spineLabel: "five stage gates",
      chips: ["budget", "funding", "risks"],
      footnote: "recorded once, cited everywhere",
    },
    outputs: [
      { label: "Monthly client report" },
      { label: "Funding bid" },
      { label: "Feasibility study" },
      { label: "Health card (PDF)", violet: true },
    ],
    outLabel: "drafted from live records",
    returnLabel:
      "every figure cites its source — you review before anything is sent",
  },
  outcomes: [
    {
      title: "Projects move through visible stage gates",
      body: "Every project sits at a named stage with what's needed to progress, so a portfolio review takes minutes and nothing stalls quietly.",
      evidence:
        "A project page with stage tracking, and a portfolio view across every engagement.",
      spot: "gates",
    },
    {
      title: "Budget, funding and risks live with the project",
      body: "Figures and risks are recorded once, against the project — not scattered across spreadsheets that disagree with each other.",
      evidence:
        "Budget, funding and risk tabs on each project, drawn on by every draft.",
      spot: "registers",
    },
    {
      title: "Reports draw from the live record",
      body: "Monthly reports, feasibility studies and funding bids are drafted from the current project data, with citations back to your source documents.",
      evidence:
        "Drafts assembled from project records and the vault, exported in your branding.",
      spot: "output",
    },
  ],
  workspace: [
    "A portfolio of development projects, each with five stage gates",
    "Budget lines, funding sources and a risk register per project",
    "The document vault: feasibility work, surveys, minutes and correspondence, all citable",
    "Confirmed organisational facts shared across every draft",
    "A health card summarising each project's status for the client",
  ],
  deliverables: [
    "Monthly client report",
    "Feasibility study",
    "Funding bid",
    "Project health card (PDF)",
    "Presentation slides",
  ],
  trust:
    "Every draft cites the document and page it drew from, and your workspace is isolated from every other customer's at the database level. You review and send everything — Flowgrid never submits anything to a funder on your behalf.",
  fit: [
    "You run several community-led development engagements at once.",
    "Clients or funders expect regular written reporting against a live project.",
    "Your evidence base is documents: surveys, minutes, studies, correspondence.",
  ],
  notFit: [
    "You need construction-phase tools like Gantt scheduling or site management.",
    "You want a system that submits applications to funders automatically — Flowgrid deliberately doesn't.",
    "Your work is one-off with no recurring reporting to reuse records for.",
  ],
  ctaHeading: "Bring one live project. We'll set it up together in the pilot.",
};

export default function GroundworkPage() {
  return <SolutionPage content={content} />;
}
