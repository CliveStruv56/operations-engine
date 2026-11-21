import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// The public marketing pages: they must work with no auth and no backend,
// the mobile menu must be a full keyboard citizen (PRD §5), and both lead
// forms must submit exactly once against /api/leads with an idempotency key
// and expose a recoverable error state (PRD §11).

interface CapturedLead {
  headers: Record<string, string>;
  body: Record<string, unknown>;
}

function captureLeads(page: Page, status = 200): CapturedLead[] {
  const captured: CapturedLead[] = [];
  page.route("**/api/leads", (route) => {
    captured.push({
      headers: route.request().headers(),
      body: route.request().postDataJSON(),
    });
    return route.fulfill({ status, json: status === 200 ? { ok: true } : { error: "boom" } });
  });
  return captured;
}

async function expectNoSeriousAccessibilityViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(
    violations.filter((v) => v.impact === "serious" || v.impact === "critical"),
  ).toEqual([]);
}

test("the homepage is public and the skip link is the first tab stop", async ({ page }) => {
  await page.goto("/");
  // No redirect to /login — the marketing h1 renders.
  await expect(
    page.getByRole("heading", { level: 1, name: /give every client an ai workspace/i }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByRole("link", { name: "See what works today" })).toHaveAttribute(
    "href",
    "#works-today",
  );
  // What works today is labelled; planned work is labelled and set apart.
  const today = page.locator("#works-today");
  await expect(today.getByText("Works today", { exact: true })).toBeVisible();
  await expect(today.getByRole("heading", { level: 3 })).toHaveCount(6);
  const next = page.getByRole("region", { name: "Being built next" });
  await expect(next.getByText("Being built next · not available yet")).toBeVisible();
  // No pilot wording, no pilot form, no security-page link (fact-check A22).
  await expect(page.locator("main").getByText(/pilot/i)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Join the pilot list" })).toHaveCount(0);
  await expect(page.locator('main a[href="/security-and-data"]')).toHaveCount(0);
  await expect(page.locator("main").getByText(/editable PowerPoint/)).toHaveText(
    "A chat answer exports as a branded PDF, and a slide-deck answer as editable PowerPoint.",
  );

  await page.keyboard.press("Tab");
  const first = page.getByRole("link", { name: "Skip to content" });
  await expect(first).toBeFocused();
  // sr-only until focused; focusing must make it visible.
  await expect(first).toBeVisible();
});

test("account creation is invite-led", async ({ page }) => {
  await page.goto("/signup");
  await expect(
    page.getByRole("heading", { name: /account creation is by invitation/i }),
  ).toBeVisible();
  await expect(page.getByLabel("Email")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /book a demo/i })).toHaveAttribute(
    "href",
    "/contact",
  );

  await page.goto("/signup?next=%2Finvite%2Fexample-token");
  await expect(page.getByRole("heading", { name: /create account/i })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();

  await page.goto("/login");
  await expect(page.getByText(/workspaces are invitation-only/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /book a demo/i })).toHaveAttribute(
    "href",
    "/contact",
  );
});

test("key public and authentication pages have no serious automated accessibility defects", async ({
  page,
}) => {
  for (const path of ["/", "/contact", "/login", "/signup"]) {
    await page.goto(path);
    await expectNoSeriousAccessibilityViolations(page);
  }
});

test("the mobile menu opens by keyboard, traps focus and Escape returns it", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");

  const toggle = page.getByRole("button", { name: "Menu" });
  await toggle.focus();
  await page.keyboard.press("Enter");

  // Open: focus moves to the first menu item.
  const menu = page.locator("#mobile-menu");
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("link", { name: "Platform" })).toBeFocused();

  // Trap: Shift+Tab from the first item wraps to the last, not out of the menu.
  await page.keyboard.press("Shift+Tab");
  await expect(menu.getByRole("link", { name: "Book a demo" })).toBeFocused();

  // Escape closes and returns focus to the toggle.
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Menu" })).toBeFocused();
});

test("the demo form submits one lead with an idempotency key", async ({ page }) => {
  const leads = captureLeads(page);
  await page.goto("/contact");

  await page.getByLabel("Name").fill("Jo Tester");
  await page.getByLabel("Work email").fill("jo@example.org.uk");
  await page.getByLabel("Organisation").fill("E2E Community Trust");
  await page.getByLabel("Which workflow?").selectOption("grants");
  await page.getByRole("button", { name: "Request a demo" }).click();

  await expect(page.getByRole("status")).toContainText(/request received/i);

  expect(leads).toHaveLength(1);
  const [lead] = leads;
  expect(lead.body).toMatchObject({
    kind: "demo",
    email: "jo@example.org.uk",
    name: "Jo Tester",
    organisation: "E2E Community Trust",
    workflow: "grants",
    sourcePage: "/contact",
  });
  // The honeypot travels empty and the key is a UUID.
  expect(lead.body.website).toBeFalsy();
  expect(lead.headers["idempotency-key"]).toMatch(/^[0-9a-f-]{36}$/);
});

// The pilot list form left the home page with the Nov 2026 rewrite (no pilot
// is running), so the recoverable-error path is pinned on the demo form.
test("the demo form fails recoverably and retries with the same key", async ({ page }) => {
  const leads = captureLeads(page, 502);
  await page.goto("/contact");

  await page.getByLabel("Name").fill("Jo Tester");
  await page.getByLabel("Work email").fill("retry@example.org.uk");
  await page.getByLabel("Organisation").fill("E2E Community Trust");
  await page.getByRole("button", { name: "Request a demo" }).click();

  // Recoverable error: an alert with the fallback address, form still usable.
  // (Filtered because Next's route announcer is also role=alert; the copy
  // uses a typographic apostrophe.)
  const alert = page.getByRole("alert").filter({ hasText: /go through/i });
  await expect(alert).toBeVisible();
  await expect(alert.getByRole("link", { name: /hello@flowgridos\.co\.uk/ })).toBeVisible();

  // Retry succeeds and reuses the same idempotency key, so the server can
  // dedupe a submission that actually landed the first time.
  await page.unroute("**/api/leads");
  const retries = captureLeads(page);
  await page.getByRole("button", { name: "Request a demo" }).click();
  await expect(page.getByRole("status")).toContainText(/request received/i);

  expect(leads).toHaveLength(1);
  expect(retries).toHaveLength(1);
  expect(retries[0].body).toMatchObject({ kind: "demo", email: "retry@example.org.uk" });
  expect(retries[0].headers["idempotency-key"]).toBe(leads[0].headers["idempotency-key"]);
});
