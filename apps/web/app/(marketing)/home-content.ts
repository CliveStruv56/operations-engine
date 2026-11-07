import type { SpotName } from "./spot-icons";
import type { WorkflowDiagramContent } from "./workflow-diagram";
import { PRODUCT_LANGUAGE } from "@/lib/product-language";

/* Home page copy (Nov 2026 rewrite). Every sentence here is approved copy
 * that passed the publication fact-check and brand-voice check of 7 Nov
 * 2026: change wording only through those checks. Several sentences describe
 * items from docs/enhancement-plan-nov-2026.md stages 2–4, so this page is
 * held until they ship (see the PR that introduced it). */

export const BEFORE_AFTER = [
  {
    before: "Hunting through folders for the latest version",
    after: "Answers that name the exact document they came from and quote the passage",
  },
  {
    before: "Typing the same charity number into every form",
    after: "Facts confirmed once and reused in every draft",
  },
  {
    before: "Starting every report from a blank page",
    after: "First drafts built from your own records and documents",
  },
  {
    before: "Monthly jobs that rely on one person remembering",
    after: "Saved routines that run on time and wait for your OK",
  },
];

export interface CapabilityCard {
  title: string;
  spot: SpotName;
  body: string;
  also?: string[];
}

export const CAPABILITIES: CapabilityCard[] = [
  {
    title: "Ask your documents and see the source",
    spot: "citation",
    body: "Stop hunting through folders: ask a question and see where the answer came from. Upload the documents your organisation runs on: policies, minutes, past bids, accounts, surveys. Ask a question in plain English and the answer names the document it came from, with the passage it used and, for PDFs, the page number. If your documents don’t hold the answer, Flowgrid says so instead of guessing.",
    also: [
      "Need to look further? With research mode (a setting that lets Flowgrid search the web) switched on for your workspace, Flowgrid reads the web pages behind the search results and names the web page behind each passage it uses.",
      "If your team already uses an AI assistant that can connect to other services, you can let it search your Flowgrid documents and confirmed facts. It can look but not change anything, and each person has their own separate access.",
    ],
  },
  {
    title: "Confirm a fact once, use it everywhere",
    spot: "claim",
    body: "Charity number, registered office, trustees, income: the details you type into form after form. Flowgrid fills many of them in from Companies House and the charity registers for England and Wales, Scotland and Northern Ireland, each with a link to its public source. You check each fact once, and every draft uses the confirmed version. Facts carry a review date, and your admins get a weekly email when any need checking.",
  },
  {
    title: "Keep work in projects, not lost chats",
    spot: "plan",
    body: `Each piece of work gets one place of its own. ${PRODUCT_LANGUAGE.core.everyProject} In plain terms, that is its own conversation, its own documents and, if you want one, a task list. Give the workspace, and each project, a short written brief: who you are, who the work is for, the words you prefer. Flowgrid reads it every time it answers. Need to keep track of something else, such as volunteers, equipment or events? Ask for a tracking list (a register) and Flowgrid sets one up that you can view as a list, a board or a calendar and use in chats and drafts.`,
  },
  {
    title: "Draft the documents you write every month",
    spot: "output",
    body: "Client reports, funding bids, monitoring returns and answers to funder forms are drafted from your project records, confirmed facts and documents, with the sources shown so you can check them. Board papers, letters and briefings start in chat, from your documents and confirmed facts. Drafts download as Word documents you can edit, and chat answers export as a branded PDF, or as editable PowerPoint when you ask for slides. Flowgrid never submits anything to a funder: you check the answers and paste them into the funder’s own form.",
  },
  {
    title: "Hand over routine work and keep the final say",
    spot: "structure",
    body: "Ask Flowgrid to add a task, update a budget line or a risk, set a deadline or start a draft, and it shows you the change as a card. Someone with the right permissions accepts it, edits it or rejects it. A job that went well can be saved as a playbook, a starting point you can reuse next time, alongside the ready-made playbooks Flowgrid provides. Any draft or check can be set to run on a schedule (“the monthly report, on the first of the month”) or when something happens (“a grant deadline is 14 days away”). We call these saved routines. Over time Flowgrid notices the edits you keep making, such as “tenants”, not “residents”, and asks whether to remember them.",
  },
  {
    title: "Work as a team, with your email and calendar",
    spot: "evidence",
    body: "Comment on a draft, a document or a fact, mention a colleague, or highlight a paragraph and ask for just that part to be rewritten. Share a useful chat with the rest of the team. Connect your email and calendar: Flowgrid drafts replies to funders and partners for a person to send, and lets you add your deadlines to your calendar. Each deadline goes in as an event only once you confirm it, and Flowgrid never invites anyone.",
    also: [
      "With your permission it can also search your inbox, without changing anything in it, and name the email it used.",
      "Flowgrid installs on your phone or computer like an app.",
    ],
  },
];

export const FIGURES = [
  {
    value: "4",
    label: "public registers Flowgrid can fill your facts in from, each fact linked to its source",
  },
  {
    value: "5",
    label: "stages, called stage gates, carrying every development project from idea to delivery",
  },
  {
    value: "0",
    label: "emails, forms or documents sent to funders, clients or partners without a person’s say-so",
  },
];

export const IN_CHARGE = [
  "Emails to funders and partners are drafted, never sent automatically. Only a person presses send.",
  "A new saved routine starts switched off until someone turns it on.",
  "Each routine has its own monthly budget and a history of every time it ran, showing the steps it took and what it cost. If it fails three times it pauses and emails its owner.",
];

export interface AudienceCard {
  title: string;
  points: string[];
  link: { label: string; href: string };
}

const EXPLORE_PLATFORM = { label: "Explore the platform", href: "/platform" };

export const AUDIENCES: AudienceCard[] = [
  {
    title: "Charities and community groups",
    points: [
      "Funder forms answered from your confirmed facts and past bids, with sources to check.",
      "Every grant’s conditions, deadlines and impact evidence in one place, with one calendar of monitoring returns across all your grants.",
      "Your charity’s details filled in from the charity registers for England and Wales, Scotland and Northern Ireland.",
      "A community profile of the place you serve: its services, facilities and figures, downloadable as a branded PDF.",
    ],
    link: {
      label: `Explore ${PRODUCT_LANGUAGE.grantwork.combined}`,
      href: PRODUCT_LANGUAGE.grantwork.href,
    },
  },
  {
    title: "Development trusts and project-led organisations",
    points: [
      "Each development project moves through five stages, called stage gates, with its budget, funding, risks and stakeholders kept on the project.",
      "Monthly client reports, feasibility studies, funding bids and a one-page health card drafted from the live project record.",
      "Grant applications as a tab on any project, including a development scheme.",
      "A task plan where each task can be given to a named person, kept up to date through changes you approve rather than re-type.",
    ],
    link: {
      label: `Explore ${PRODUCT_LANGUAGE.groundwork.combined}`,
      href: PRODUCT_LANGUAGE.groundwork.href,
    },
  },
  {
    title: "Professional firms, such as accountants and agencies",
    points: [
      "A project for each client, with its own chat, documents and task plan, and the client’s contacts as a tab on the project.",
      "Client reports and presentations started in chat from your documents and confirmed facts, and exported as branded PDFs or slides.",
      "A brief for each client, so answers use the right names and tone.",
      "Your own playbooks for recurring jobs, shared with colleagues when you’re ready.",
      "Monthly jobs that run on schedule and arrive as drafts for review.",
      "Flowgrid works beside your accounts and practice software. It doesn’t replace them or connect to them.",
    ],
    link: EXPLORE_PLATFORM,
  },
  {
    title: "Other small businesses",
    points: [
      "Your policies, procedures and past proposals become answerable, with the source shown for every answer drawn from them.",
      "Company details from Companies House, kept as confirmed facts.",
      "Projects, plans and registers for whatever you need to track.",
      "Answers exported as PDFs or editable PowerPoint in your own branding.",
    ],
    link: EXPLORE_PLATFORM,
  },
];

export const STEPS: { label: string; title: string; body: string; spot: SpotName }[] = [
  {
    label: "Step 1 · Set up",
    title: "Tell Flowgrid who you are",
    body: "When you first sign in, the setup guide suggests your organisation from your email address, looks for it on Companies House or the Charity Commission register, and asks you to confirm the match. Confirm it and your basic facts are filled in. The guide then helps you invite colleagues, asks for one job you need done this week, and starts it with you.",
    spot: "evidence",
  },
  {
    label: "Step 2 · Bring the evidence",
    title: "Add documents and a brief",
    body: "Add your documents and write a short brief for the workspace and each project. Everything is stored in your own workspace, separate from every other customer’s.",
    spot: "structure",
  },
  {
    label: "Step 3 · Produce and review",
    title: "Check it, then send it yourself",
    body: "Ask your question or ask for a draft, then check each answer against the source it points to. Accept the changes you agree with, and export answers as branded PDFs or slides.",
    spot: "output",
  },
];

export const WORKSPACE_DIAGRAM: WorkflowDiagramContent = {
  ariaLabel:
    "Your documents and confirmed organisational facts flow into one structured workspace of projects, plans and registers. Cited answers, client reports, funding bids and branded exports are produced out of it, and every output cites its source for you to review before anything leaves.",
  vault: {
    caption: "policies · minutes · reports",
    arrowLabel: "source and passage named",
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
    chips: ["projects", "facts", "registers"],
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

export const COSTS = [
  "Every time Flowgrid uses AI, including background work such as reading a new document, it is recorded with its cost. Nothing runs uncounted.",
  "The cost of each answer is shown beneath it.",
  "Everyday questions go to a low-cost option by default; heavier work, such as reports and analysis, goes to stronger options that cost more.",
  "Each workspace has a monthly budget. Once it’s reached, chat switches to Flowgrid’s low-cost default and shows a notice.",
  "The monthly workspace report puts what Flowgrid produced (answers with their sources, drafts, funder forms answered, deadlines met) beside what it cost, by project and module, as a page and as a PDF ready for trustees or partners.",
];

export const TRUST = [
  "Your workspace is kept separate from every other customer’s. The separation is built into the way the information is stored, not only into the screens you see.",
  "Roles and permissions limit what each person can see and do.",
  "Answers name the document and passage they came from, and say so when they can’t.",
  "Admins can download the workspace’s documents, drafts and records as one archive.",
  "If you connect your own AI assistant, it can search your documents and confirmed facts but not change them.",
];
