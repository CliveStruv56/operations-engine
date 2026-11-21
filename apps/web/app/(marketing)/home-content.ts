import type { SpotName } from "./spot-icons";
import { PRODUCT_LANGUAGE } from "@/lib/product-language";

/* Home page copy (consultancy-first rewrite, 21 Nov 2026). Every visible
 * string on the home page lives here, word for word as it passed the
 * publication fact-check: change wording only through that check, and keep
 * each change to one line of this file. Nothing here may describe a
 * "being built next" item as available. */

export const HOME_META = {
  title: "Flowgrid OS: AI workspaces that show their sources",
  description:
    "A separate AI workspace for each organisation, with answers from its own documents, confirmed facts and projects. For consultancies and their clients, and for small businesses.",
};

export const HERO = {
  kicker: "For consultancies and the small businesses they serve",
  headline: "Give every client an AI workspace that shows its sources.",
  subline:
    "Each organisation gets its own workspace: answers from its own documents with the source named, facts confirmed once, and projects that keep the work together. Run it for your clients, or for your own business.",
  primaryCta: "Book a 20-minute demo",
  secondaryCta: { label: "See what works today", href: "#works-today" },
  smallPrint:
    "AI drafts. People decide. Nothing goes to a client or funder without a person’s say-so.",
};

export interface LinkItem {
  label: string;
  href: string;
}

export interface AudienceCard {
  title: string;
  points: string[];
  links: LinkItem[];
}

export const AUDIENCES_TITLE = "Who it’s for";

export const AUDIENCES: AudienceCard[] = [
  {
    title: "Consultancies and advisers: run it for your clients",
    points: [
      "We set up a separate workspace for each client, kept apart from every other customer’s inside the database.",
      "Your team is invited in, and we switch on the modules each client needs.",
    ],
    links: [{ label: "Ask about running Flowgrid for your clients", href: "/contact" }],
  },
  {
    title: "Small businesses: use it for your own work",
    points: [
      "Your policies, procedures and past proposals become answerable, with the source named.",
    ],
    links: [{ label: "Explore the platform", href: "/platform" }],
  },
  {
    title: "The fields we serve",
    points: [
      "Professional firms and agencies: the core platform, with no sector module needed.",
      "Groundwork · Development projects: five stage gates, with budget, funding and risks on each project.",
      "Grantwork · Grant funding: applications, award conditions, impact evidence and monitoring returns.",
      "Charities and development trusts: your organisation’s details, kept as confirmed facts.",
    ],
    // Held back until Clive confirms: both solution pages still say "Discuss
    // a pilot" and offer to pilot the work, and no pilot is running. To
    // restore, put these back:
    //   { label: "Explore Groundwork", href: "/solutions/groundwork" },
    //   { label: "Explore Grantwork", href: "/solutions/grantwork" },
    links: [],
  },
];

export interface CapabilityCard {
  title: string;
  spot: SpotName;
  body: string;
}

export const WORKS_TODAY = {
  label: "Works today",
  title: "What works today",
  cards: [
    {
      title: "Ask your documents and see the source",
      spot: "citation",
      body: "In chat, every citation to your documents names the document and the passage it came from, with the page for PDFs, and when your documents don’t hold the answer, Flowgrid says so.",
    },
    {
      title: "Confirm a fact once, reuse it in drafts",
      spot: "claim",
      body: "Keep your organisation’s details as facts a person has confirmed.",
    },
    {
      title: "Keep work in projects",
      spot: "plan",
      // Ruling #71: the PRODUCT_LANGUAGE.core sentence, verbatim.
      body: PRODUCT_LANGUAGE.core.everyProject,
    },
    {
      title: "Draft the documents you write every month",
      spot: "output",
      body: "With Groundwork · Development projects, client reports, feasibility studies and funding bids are drafted from the live project record.",
    },
    {
      title: "Export in your branding",
      spot: "export",
      body: "A chat answer exports as a branded PDF, and a slide-deck answer as editable PowerPoint.",
    },
    {
      title: "Model choice in chat",
      spot: "structure",
      body: "Chat picks a model by task and by length, and everyday questions go to a low-cost one by default.",
    },
  ] satisfies CapabilityCard[],
};

/** A sentence with some phrases set in bold. */
export type RichLine = { text: string; strong?: boolean }[];

export const BUILT_NEXT = {
  label: "Being built next · not available yet",
  title: "Being built next",
  intro:
    "These are in our current build plan. They are not in the product today, and we don’t give delivery dates.",
  items: [
    [
      { text: "Approval cards:", strong: true },
      {
        text: " Flowgrid proposes a change, such as a new task or a budget line, and a person accepts, edits or rejects it.",
      },
    ],
    [
      { text: "Saved routines", strong: true },
      { text: " for monthly jobs, which start switched off until a person turns them on." },
    ],
    [
      { text: "Email replies drafted", strong: true },
      { text: " for a person to send, " },
      { text: "deadlines added to your calendar", strong: true },
      { text: ", and a " },
      { text: "read-only connection", strong: true },
      { text: " for your client’s own AI assistant." },
    ],
  ] satisfies RichLine[],
};

export const IN_CHARGE = {
  title: "You stay in charge",
  points: [
    "Three roles, owner, admin and member, limit what each person can do, and modules are switched on per workspace.",
    "The AI can get things wrong. That’s why every citation names its source, so a person can check a statement before it is used.",
  ],
};

export const TRUST = {
  title: "Your data, plainly",
  points: [
    "Each workspace is kept separate, and the separation is enforced inside the database, not only by application code.",
    "Commercial guarantees about our model providers match the signed terms in your agreement, not this page.",
  ],
};

export const CLOSING = {
  title: "Bring one client’s repeated job. We’ll show you how it fits.",
  body: "A 20-minute conversation around a report, bid or return that you or your client already produce.",
  primaryCta: "Book a 20-minute demo",
  secondaryCta: { label: "Ask about running Flowgrid for your clients", href: "/contact" },
};
