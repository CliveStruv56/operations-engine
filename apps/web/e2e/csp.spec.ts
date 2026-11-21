import { expect, test, type Page } from "@playwright/test";
import { SCREENS, fixture, mockBackend } from "./mock-backend";

// F3 (docs/enhancement-plan-nov-2026.md, code review item 13): the
// Content-Security-Policy must not refuse anything the site really loads.
// Every main marketing, auth and app screen is loaded, and the flows that
// reach other origins are run — the streamed chat answer (API), a document
// upload (presigned PUT to storage), the tenant logo (storage) and a lead
// form (this site). Any CSP violation fails the test, whether the policy is
// enforced or report-only: both fire `securitypolicyviolation`.
//
// The normal e2e run uses the dev server. The real risk is in a production
// build, where a page prerendered without a nonce would lose every script,
// so CI also runs this file against `next build && next start`:
//   E2E_PROD=1 pnpm test:e2e e2e/csp.spec.ts

const STORAGE = "http://localhost:9997"; // NEXT_PUBLIC_STORAGE_ORIGIN in playwright.config.ts

const MARKETING = [
  "/",
  "/platform",
  "/about",
  "/contact",
  "/solutions/groundwork",
  "/solutions/grantwork",
  "/security-and-data",
  "/privacy",
  "/terms",
  "/cookies",
];
const AUTH = ["/login", "/signup", "/signup?next=%2Finvite%2Fexample-token", "/invite/example-token"];
const APP = SCREENS.map((s) => s.path).filter((p) => p.startsWith("/app") || p === "/admin");

type Violation = { directive: string; blocked: string; disposition: string; page: string };

/** Records every CSP violation the page reports, and console lines about
 * refused content. `collect()` moves the current page's violations into the
 * running list — call it before each navigation, which resets the page. */
async function watchCsp(page: Page) {
  const logged: string[] = [];
  const violations: Violation[] = [];
  page.on("console", (m) => {
    if (/content security policy|refused to/i.test(m.text())) logged.push(m.text().slice(0, 300));
  });
  await page.addInitScript(() => {
    const w = window as unknown as { __csp: unknown[] };
    w.__csp = [];
    document.addEventListener("securitypolicyviolation", (e) => {
      w.__csp.push({
        directive: e.effectiveDirective,
        blocked: e.blockedURI,
        disposition: e.disposition,
        page: location.pathname,
      });
    });
  });
  const collect = async () => {
    violations.push(
      ...(await page.evaluate(() =>
        ((window as unknown as { __csp?: Violation[] }).__csp ?? []).splice(0)
      ))
    );
    return { violations, logged };
  };
  return {
    collect,
    /** Loads a path, waits for it to settle, and collects. */
    async visit(path: string) {
      const resp = await page.goto(path);
      expect(resp?.ok(), `${path} loads`).toBeTruthy();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(300);
      return collect();
    },
  };
}

test("every page carries a fresh nonce policy, and every script carries the nonce", async ({
  request,
}) => {
  const policies: string[] = [];
  for (const path of ["/", "/contact", "/login", "/app"]) {
    const resp = await request.get(path);
    const policy =
      resp.headers()["content-security-policy-report-only"] ??
      resp.headers()["content-security-policy"];
    expect(policy, path).toBeTruthy();
    const scriptSrc = policy.split("; ").find((d) => d.startsWith("script-src "))!;
    const nonce = scriptSrc.match(/'nonce-([^']+)'/)?.[1];
    expect(nonce, `${path} script-src has a nonce`).toBeTruthy();
    expect(scriptSrc).toContain("'strict-dynamic'");
    expect(scriptSrc).not.toContain("unsafe-inline");
    expect(policy).toMatch(/connect-src [^;]*http:\/\/localhost:9998/); // the API
    expect(policy).toMatch(/connect-src [^;]*http:\/\/localhost:9999/); // Supabase
    expect(policy).toContain(`connect-src 'self'`);
    expect(policy).toContain("frame-ancestors 'none'");
    // Prerendered HTML would have no nonce on its scripts: each one must.
    const html = await resp.text();
    // The 12 Oct baseline as a <meta> policy, enforced even while the
    // header policy is report-only.
    expect(html).toContain('<meta http-equiv="Content-Security-Policy" content="base-uri');
    const scripts = html.match(/<script\b[^>]*>/g) ?? [];
    expect(scripts.length, path).toBeGreaterThan(0);
    for (const tag of scripts) expect(tag, `${path}: ${tag}`).toContain(`nonce="${nonce}"`);
    policies.push(nonce!);
  }
  expect(new Set(policies).size, "a new nonce per request").toBe(policies.length);
});

test("marketing and sign-in pages load with no CSP violations", async ({ page }) => {
  const csp = await watchCsp(page);
  for (const path of [...MARKETING, ...AUTH]) await csp.visit(path);
  expect(await csp.collect()).toEqual({ violations: [], logged: [] });
});

test("the main app screens load with no CSP violations", async ({ page }) => {
  test.setTimeout(180_000);
  const csp = await watchCsp(page);
  await mockBackend(page);
  for (const path of APP) await csp.visit(path);
  expect(await csp.collect()).toEqual({ violations: [], logged: [] });
});

test("chat streaming, uploads, the storage logo and a lead form pass the policy", async ({
  page,
}) => {
  const csp = await watchCsp(page);
  await mockBackend(page);
  const tenant = fixture("GET", "/tenants/me") as Record<string, unknown>;
  await page.route("**/api/v1/tenants/me", (r) =>
    r.fulfill({ json: { ...tenant, logo_url: `${STORAGE}/bucket/logo.png?X-Amz-Signature=x` } })
  );
  const storage: string[] = [];
  await page.route(`${STORAGE}/**`, (r) => {
    storage.push(`${r.request().method()} ${new URL(r.request().url()).pathname}`);
    if (r.request().method() === "PUT") return r.fulfill({ status: 200, body: "" });
    // A 1x1 transparent PNG.
    return r.fulfill({
      contentType: "image/png",
      body: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
        "base64"
      ),
    });
  });

  // The streamed answer: fetch() to the API, read as server-sent events.
  await page.route("**/api/v1/conversations/c1/messages", (r) => {
    if (r.request().method() !== "POST") return r.fallback();
    const done = {
      id: "m9",
      role: "assistant",
      content: "Streamed answer.",
      citations: [],
      model: null,
      cost_usd: null,
    };
    return r.fulfill({
      contentType: "text/event-stream",
      body:
        `event: delta\ndata: ${JSON.stringify({ content: "Streamed " })}\n\n` +
        `event: done\ndata: ${JSON.stringify(done)}\n\n`,
    });
  });
  await csp.visit("/app?c=c1");
  await page.getByLabel("Message").fill("Summarise the policy");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Streamed answer.")).toBeVisible();
  await csp.collect();

  // A document upload: presigned PUT straight to the storage host.
  await page.route("**/api/v1/documents", (r) =>
    r.request().method() === "POST"
      ? r.fulfill({ json: { id: "d9", upload_url: `${STORAGE}/bucket/t/d9?X-Amz-Signature=x` } })
      : r.fallback()
  );
  await page.route("**/api/v1/documents/d9/complete", (r) => r.fulfill({ json: {} }));
  await csp.visit("/app?view=vault");
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hello") });
  await expect.poll(() => storage).toContain("PUT /bucket/t/d9");
  // The presigned tenant logo, from the storage host, in the sidebar.
  await expect.poll(() => storage).toContain("GET /bucket/logo.png");
  await csp.collect();

  // A lead form posts to this site.
  await page.route("**/api/leads", (r) => r.fulfill({ json: { ok: true } }));
  await csp.visit("/contact");
  await page.getByLabel("Name").fill("Jo Tester");
  await page.getByLabel("Work email").fill("jo@example.org.uk");
  await page.getByLabel("Organisation").fill("E2E Community Trust");
  await page.getByLabel("Which workflow?").selectOption("grants");
  await page.getByRole("button", { name: "Request a demo" }).click();
  await expect(page.getByRole("status")).toContainText(/request received/i);
  expect(await csp.collect()).toEqual({ violations: [], logged: [] });
});

test("the check itself catches a refused connection", async ({ page }) => {
  // Guards the other tests against passing vacuously: a fetch to an origin
  // outside connect-src must be reported.
  const csp = await watchCsp(page);
  await csp.visit("/");
  await page.evaluate(() => fetch("https://not-allowed.example/x").catch(() => undefined));
  await expect
    .poll(async () => (await csp.collect()).violations.map((v) => v.directive))
    .toContain("connect-src");
});
