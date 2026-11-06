import { mkdirSync, writeFileSync } from "node:fs";
import { test, type Page } from "@playwright/test";

// F1 visual pass (docs/enhancement-plan-nov-2026.md): full-page screenshots of
// every main screen at laptop and phone width, against the same fully mocked
// backend the other specs use, plus a few automatic checks per screen
// (horizontal overflow, text under 12px, H1 and <main>, console errors).
//
// Opt-in, so it never slows the normal e2e run:
//   VISUAL_PASS=1 pnpm test:e2e e2e/visual-pass.spec.ts
// Output: test-results/visual-pass/<width>/<screen>.png and checks.json.

test.skip(!process.env.VISUAL_PASS, "set VISUAL_PASS=1 to run the visual pass");

const OUT = "test-results/visual-pass";
const T = "2026-11-04T10:15:00Z";
const TENANT_ID = "11111111-1111-4111-8111-111111111111";

const TENANT = {
  id: TENANT_ID,
  name: "Riverside Community Trust",
  plan: "core",
  seats: 5,
  brand: {},
  features: { projects: true, grants: true, contacts: true, community: true, web_search: true },
  trial_ends_at: null,
  role: "owner",
  logo_url: null,
};

const project = (o: Record<string, unknown>) => ({
  description: null,
  archived: false,
  document_count: 0,
  kind: "general",
  kind_available: true,
  stage_current: null,
  is_development: false,
  has_plan: false,
  open_task_count: 0,
  updated_at: T,
  ...o,
});

const PROJECTS = [
  project({
    id: "p1",
    name: "Mill Lane community homes",
    kind: "development",
    is_development: true,
    stage_current: "plan",
    document_count: 14,
    description: "Twelve affordable homes on the former depot site.",
  }),
  project({
    id: "p2",
    name: "Lottery reaching communities bid",
    document_count: 6,
    has_plan: true,
    open_task_count: 4,
    description: "Three-year bid for the youth programme.",
  }),
  project({ id: "p3", name: "Trustee recruitment 2027", document_count: 2 }),
];

const KINDS = {
  kinds: [
    {
      key: "general",
      label: "General project",
      description: "Chat and documents, with an optional plan of tasks.",
      home: "chat",
      create: "inline",
      upgrades_to: ["development"],
      available: true,
    },
    {
      key: "development",
      label: "Development project",
      description: "A housing or building scheme, from site to homes.",
      home: "room",
      create: "setup",
      upgrades_to: [],
      available: true,
    },
  ],
  addons: [
    { key: "contacts", label: "Contacts", description: "Link contacts and companies to a project.", available: true },
    { key: "grants", label: "Grant applications", description: "Track the grant applications made for a project.", available: true },
  ],
};

const CONVERSATIONS = [
  ["c1", "What does our safeguarding policy say about lone working?", null],
  ["c2", "Summarise the Mill Lane planning conditions", "p1"],
  ["c3", "Draft a trustee recruitment advert", "p3"],
  ["c4", "Reserves position at year end", null],
].map(([id, title, project_id]) => ({
  id,
  title,
  project_id,
  visibility: "private",
  is_mine: true,
  owner_email: "sam@riverside.example",
  updated_at: T,
}));

const MESSAGES = [
  {
    id: "m1",
    role: "user",
    content: "What does our safeguarding policy say about lone working?",
    citations: [],
    model: null,
    cost_usd: null,
  },
  {
    id: "m2",
    role: "assistant",
    content:
      "The safeguarding policy sets three rules for lone working with young people [1]:\n\n" +
      "1. **No unplanned one-to-one sessions.** A second adult must know where the session is and when it ends [1].\n" +
      "2. **Sign in and out.** Staff record the start and end time on the shared rota, and the duty lead checks it [2].\n" +
      "3. **Escalation.** If a worker has not signed out within 30 minutes, the duty lead phones them, then the designated safeguarding lead [2].\n\n" +
      "The policy was last reviewed in March 2026 and is due for review in March 2027 [1].",
    citations: [
      {
        n: 1,
        chunk_id: "k1",
        document_id: "d1",
        title: "Safeguarding policy 2026",
        page_start: 4,
        page_end: 5,
        snippet: "Staff and volunteers must not hold unplanned one-to-one sessions with young people…",
      },
      {
        n: 2,
        chunk_id: "k2",
        document_id: "d2",
        title: "Lone working procedure",
        page_start: 2,
        page_end: 2,
        snippet: "Every session is signed in and out on the shared rota. The duty lead checks…",
      },
    ],
    model: "workhorse",
    cost_usd: 0.0021,
  },
];

const doc = (id: string, title: string, mime: string, status: string, project_id: string | null) => ({
  id,
  title,
  mime,
  project_id,
  is_primary: false,
  summary: status === "ready" ? `${title}: key points summarised for search.` : null,
  status,
  error: status === "failed" ? "The file could not be read." : null,
  created_at: T,
  has_source: true,
  conversation_id: null,
});

const DOCUMENTS = [
  doc("d1", "Safeguarding policy 2026", "application/pdf", "ready", null),
  doc("d2", "Lone working procedure", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "ready", null),
  doc("d3", "Annual accounts 2024-25", "application/pdf", "ready", null),
  doc("d4", "Mill Lane planning decision notice", "application/pdf", "embedding", "p1"),
  doc("d5", "Board minutes October", "text/plain", "failed", null),
];

const MEMBERS = [
  ["mem1", "owner", "sam@riverside.example"],
  ["mem2", "admin", "priya@riverside.example"],
  ["mem3", "member", "tom@riverside.example"],
].map(([id, role, email]) => ({
  id,
  user_id: `u-${id}`,
  role,
  email,
  created_at: T,
  digest_opt_out: false,
}));

const claim = (o: Record<string, unknown>) => ({
  subject: null,
  period: null,
  value: null,
  unit: null,
  as_of: "2026-04-01",
  expires_on: null,
  status: "confirmed",
  source: "register",
  source_ref: "https://find-and-update.company-information.service.gov.uk/company/01234567",
  source_document_id: null,
  source_document_title: null,
  source_chunk_id: null,
  owner_membership_id: "mem1",
  last_verified: "2026-10-01",
  next_review: "2027-04-01",
  notes: null,
  stale: false,
  expired: false,
  ...o,
});

const CLAIMS = [
  claim({ id: "cl1", kind: "legal_name", label: "Legal name", category: "identity", statement: "Riverside Community Trust Ltd" }),
  claim({ id: "cl2", kind: "charity_number", label: "Charity number", category: "identity", statement: "Registered charity 1123456" }),
  claim({ id: "cl3", kind: "trustee", label: "Trustee", category: "governance", subject: "Ann Patel", statement: "Ann Patel is a trustee (chair)." }),
  claim({ id: "cl4", kind: "income", label: "Annual income", category: "finance", period: "2024/25", statement: "Income of £412,000 in 2024/25.", source: "document", source_document_title: "Annual accounts 2024-25", stale: true }),
  claim({ id: "cl5", kind: "insurance", label: "Public liability insurance", category: "assurance", statement: "Public liability cover of £5m.", expired: true, expires_on: "2026-09-30", source: "typed" }),
  claim({ id: "cl6", kind: "volunteers", label: "Volunteers", category: "people", statement: "62 regular volunteers.", status: "proposed", source: "draft" }),
];

const ACTIVITY = [
  { action: "documents.uploaded", actor_email: "priya@riverside.example", target_type: "document", target_id: "d3", target_title: "Annual accounts 2024-25", meta: {}, created_at: T },
  { action: "claims.confirmed", actor_email: "sam@riverside.example", target_type: "claim", target_id: "cl1", target_title: "Legal name", meta: {}, created_at: T },
  { action: "projects.created", actor_email: "tom@riverside.example", target_type: "project", target_id: "p3", target_title: "Trustee recruitment 2027", meta: {}, created_at: T },
];

const bucket = (key: string, cost: number, requests: number) => ({
  key,
  tokens_in: requests * 1800,
  tokens_out: requests * 420,
  cost_usd: cost,
  requests,
});
const USAGE = {
  month: "2026-11",
  tokens_in: 512_000,
  tokens_out: 118_000,
  cost_usd: 3.42,
  requests: 284,
  by_user: [bucket("u-mem1", 2.1, 160), bucket("u-mem2", 0.98, 90), bucket("u-mem3", 0.34, 34)],
  by_model: [bucket("workhorse", 1.2, 190), bucket("drafter", 1.6, 22), bucket("embedder", 0.12, 60), bucket("exa", 0.5, 12)],
};

const PLAN_TASKS = [
  ["t1", "Confirm match funding letter", "doing", "2026-11-20", "mem2"],
  ["t2", "Collect three years of outcomes data", "todo", "2026-11-28", "mem3"],
  ["t3", "Draft the project budget", "todo", null, null],
  ["t4", "Agree the evaluation partner", "todo", "2026-12-05", "mem1"],
  ["t5", "Read the funder guidance", "done", null, "mem1"],
].map(([id, title, status, due_date, a], position) => ({
  id,
  project_id: "p2",
  title,
  details: null,
  status,
  due_date,
  assignee_membership_id: a,
  assignee_email: MEMBERS.find((m) => m.id === a)?.email ?? null,
  position,
  completed_at: status === "done" ? T : null,
  created_at: T,
}));

const RAG = { programme: "green", cost: "amber", risk: "red" };
const DEV_ROW = {
  id: "p1",
  name: "Mill Lane community homes",
  client_org: "Riverside Community Trust",
  status: "active",
  dormancy_reason: null,
  stage_current: "plan",
  homes_planned: 12,
  target_completion: "2028-09-30",
  rag: RAG,
  next_milestone: { title: "Submit reserved matters", due_date: "2026-12-15" },
  open_risks: 3,
  outstanding_pre_commencement: 4,
  overdue_tasks: 1,
  updated_at: T,
};
const DEV_DETAIL = {
  ...DEV_ROW,
  project_type: "new_build",
  delivery_route: "design_and_build",
  site_address: "Former depot, Mill Lane, Riverside RS1 4AB",
  start_date: "2025-03-01",
  applicability: {},
  contract_facts: {},
};

const GRANT_ROW = {
  id: "g1",
  title: "Youth programme 2027–2030",
  funder_id: "f1",
  funder_name: "National Lottery Community Fund",
  status: "drafting",
  stage_current: "apply",
  amount_requested: 240000,
  amount_awarded: null,
  restricted: true,
  deadline: "2026-12-12",
  updated_at: T,
  weighted_value: 96000,
  open_conditions: 0,
  overdue_returns: 0,
  next_return_due: null,
};
const GRANT = {
  ...GRANT_ROW,
  project_id: "p2",
  project_name: "Lottery reaching communities bid",
  reference: null,
  application_type: "grant",
  programme_key: null,
  submitted_at: null,
  decision_at: null,
  start_date: "2027-04-01",
  end_date: "2030-03-31",
  reporting_note: null,
  notes: null,
  created_at: T,
};

const CONTACTS = [
  ["ct1", "Helen Ward", "National Lottery Community Fund", "Funding officer", ["funder"]],
  ["ct2", "Raj Singh", "Riverside Borough Council", "Planning officer", ["council", "mill-lane"]],
  ["ct3", "Joanna Lee", null, "Volunteer coordinator", []],
].map(([id, name, company_name, job_title, tags]) => ({
  id,
  name,
  company_id: company_name ? `co-${id}` : null,
  company_name,
  job_title,
  email: `${String(name).split(" ")[0].toLowerCase()}@example.org`,
  phone: "020 7946 0000",
  mobile: null,
  address: null,
  notes: null,
  tags,
  project_ids: [],
  created_by: null,
  created_at: T,
  updated_at: T,
}));

/** Answers every /api/v1 call. Unknown paths get [] and are recorded so the
 *  report can say which screens were shown with missing fixtures. */
function fixture(method: string, path: string): unknown {
  if (method !== "GET") return {};
  const p = path.replace(/\?.*$/, "");
  const table: Record<string, unknown> = {
    "/tenants/me": TENANT,
    "/projects": PROJECTS,
    "/project-kinds": KINDS,
    "/conversations": CONVERSATIONS,
    "/conversations/c1": CONVERSATIONS[0],
    "/conversations/c1/messages": MESSAGES,
    "/claims/summary": { needs_attention: 3, stale: 1, expired: 1, proposals: 1 },
    "/claims": CLAIMS,
    "/activity": ACTIVITY,
    "/documents": DOCUMENTS,
    "/members": MEMBERS,
    "/usage/summary": USAGE,
    "/modules": [
      { flag: "projects", label: "Development projects", kinds: [{ key: "development", label: "Development project" }], addons: [], enabled: true },
      { flag: "grants", label: "Grant applications", kinds: [], addons: ["Grant applications"], enabled: true },
      { flag: "contacts", label: "Contacts", kinds: [], addons: ["Contacts"], enabled: true },
      { flag: "community", label: "Community profile", kinds: [], addons: [], enabled: true },
      { flag: "web_search", label: "Web search", kinds: [], addons: [], enabled: false },
    ],
    "/projects/p2/plan-tasks": PLAN_TASKS,
    "/projects/portfolio": [DEV_ROW],
    "/projects/p1/groundwork": DEV_DETAIL,
    "/grants/applications": [GRANT_ROW],
    "/grants/applications/g1": GRANT,
    "/contacts": CONTACTS,
    "/companies": [],
    "/community/profile": null,
    "/question-sets": [
      { key: "nlcf-reaching", name: "Reaching Communities — full application", funder: "National Lottery Community Fund", stage: "full", source_url: null, status: "current", questions: [], last_verified: "2026-10-01", next_review: "2027-01-01", stale: false, source: "platform" },
      { key: "council-small", name: "Small grants — expression of interest", funder: "Riverside Borough Council", stage: "eoi", source_url: null, status: "current", questions: [], last_verified: "2026-06-01", next_review: "2026-09-01", stale: true, source: "tenant" },
    ],
  };
  return p in table ? table[p] : undefined;
}

type Screen = { name: string; path: string; ready?: (page: Page) => Promise<void> };

const SCREENS: Screen[] = [
  { name: "marketing-home", path: "/" },
  { name: "login", path: "/login" },
  { name: "chat-start", path: "/app" },
  { name: "chat-answer", path: "/app?c=c1" },
  { name: "chat-project", path: "/app?project=p2" },
  { name: "documents", path: "/app?view=vault" },
  { name: "organisation-facts", path: "/app/claims" },
  { name: "funder-forms", path: "/app/forms" },
  { name: "contacts", path: "/app/contacts" },
  { name: "community", path: "/app/community" },
  { name: "funding", path: "/app/grants" },
  { name: "funding-new", path: "/app/grants/new" },
  { name: "funding-application", path: "/app/grants/g1" },
  { name: "projects", path: "/app/projects" },
  { name: "projects-all", path: "/app/projects/all" },
  { name: "projects-new", path: "/app/projects/new" },
  { name: "project-general", path: "/app/projects/p2" },
  { name: "project-development", path: "/app/projects/p1" },
  { name: "usage", path: "/app/usage" },
  { name: "settings", path: "/app/settings" },
  { name: "admin", path: "/admin" },
];

const WIDTHS = [
  { label: "laptop", width: 1280, height: 800 },
  { label: "phone", width: 390, height: 844 },
];

type Check = {
  screen: string;
  width: string;
  overflowPx: number;
  smallText: string[];
  h1: number;
  main: number;
  consoleErrors: string[];
  missingFixtures: string[];
};
const results: Check[] = [];

test.describe.configure({ mode: "serial" });

for (const w of WIDTHS) {
  for (const s of SCREENS) {
    test(`${w.label} ${s.name}`, async ({ page }) => {
      const missing = new Set<string>();
      const errors: string[] = [];
      page.on("console", (m) => {
        if (m.type() === "error") errors.push(m.text().slice(0, 600));
      });
      page.on("pageerror", (e) => errors.push(`pageerror: ${e.message.slice(0, 200)}`));
      await page.setViewportSize({ width: w.width, height: w.height });
      await page.addInitScript((id) => localStorage.setItem("tenantId", id), TENANT_ID);
      await page.route("**/auth/v1/**", (r) => r.fulfill({ json: { user: null } }));
      await page.route("**/api/v1/**", (r) => {
        const u = new URL(r.request().url());
        const path = u.pathname.replace("/api/v1", "");
        const body = fixture(r.request().method(), path + u.search);
        if (body === undefined) {
          missing.add(path);
          return r.fulfill({ json: [] });
        }
        return r.fulfill({ json: body });
      });

      await page.goto(s.path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(800);
      await s.ready?.(page);

      const dir = `${OUT}/${w.label}`;
      mkdirSync(dir, { recursive: true });
      // The workspace scrolls inside its panels, not the page, so a full-page
      // shot would stop at the fold: grow the viewport to the tallest
      // scrolled panel first (capped so a runaway list stays readable).
      const tallest = await page.evaluate(() =>
        Math.max(
          document.documentElement.scrollHeight,
          ...Array.from(document.querySelectorAll("*")).map((el) => {
            const cs = getComputedStyle(el);
            return /(auto|scroll)/.test(cs.overflowY) ? el.scrollHeight + 120 : 0;
          })
        )
      );
      await page.setViewportSize({ width: w.width, height: Math.min(Math.max(tallest, w.height), 4000) });
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${dir}/${s.name}.png`, fullPage: true });
      await page.setViewportSize({ width: w.width, height: w.height });

      const m = await page.evaluate(() => {
        const doc = document.documentElement;
        const small = new Set<string>();
        for (const el of Array.from(document.querySelectorAll("body *"))) {
          const own = Array.from(el.childNodes).some(
            (n) => n.nodeType === 3 && (n.textContent ?? "").trim().length > 1
          );
          if (!own) continue;
          const cs = getComputedStyle(el);
          if (cs.visibility === "hidden" || cs.display === "none") continue;
          const r = (el as HTMLElement).getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          if (parseFloat(cs.fontSize) < 12)
            small.add(`${cs.fontSize} "${(el.textContent ?? "").trim().slice(0, 30)}"`);
        }
        return {
          overflowPx: Math.max(0, doc.scrollWidth - doc.clientWidth),
          smallText: [...small].slice(0, 8),
          h1: document.querySelectorAll("h1").length,
          main: document.querySelectorAll("main").length,
        };
      });
      results.push({
        screen: s.name,
        width: w.label,
        ...m,
        consoleErrors: errors.slice(0, 5),
        missingFixtures: [...missing],
      });
      writeFileSync(`${OUT}/checks.json`, JSON.stringify(results, null, 2));
    });
  }
}

test(`phone drawer open`, async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript((id) => localStorage.setItem("tenantId", id), TENANT_ID);
  await page.route("**/auth/v1/**", (r) => r.fulfill({ json: { user: null } }));
  await page.route("**/api/v1/**", (r) => {
    const u = new URL(r.request().url());
    const body = fixture(r.request().method(), u.pathname.replace("/api/v1", "") + u.search);
    return r.fulfill({ json: body ?? [] });
  });
  await page.goto("/app");
  await page.waitForLoadState("networkidle");
  const toggle = page.getByRole("button", { name: /menu|navigation|open/i }).first();
  if (await toggle.isVisible()) await toggle.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/phone/drawer-open.png` });
});
