import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Keyboard reachability of the workspace shell: repeated Tab presses must
// advance focus through the sidebar — past the "Your organisation" link and
// its unverified-count badge — and on into the main content, never sticking
// on one element. Regression test for a reported focus trap.

const TENANT = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "E2E Trust",
  plan: "core",
  seats: 5,
  brand: {},
  features: {},
  trial_ends_at: null,
  role: "owner",
  logo_url: null,
};

test.beforeEach(async ({ page }) => {
  await page.route("**/auth/v1/**", (route) =>
    route.fulfill({ status: 200, json: { user: null } })
  );
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    if (path === "/tenants/me") return route.fulfill({ json: TENANT });
    if (path === "/claims/summary")
      // A non-zero count so the badge — the suspected focus thief — renders.
      return route.fulfill({ json: { needs_attention: 2, stale: 1, expired: 1, proposals: 0 } });
    return route.fulfill({ json: [] });
  });
});

test("Tab advances through the sidebar into the main content", async ({ page }) => {
  await page.goto("/app");
  await expect(page.getByRole("link", { name: /your organisation —/i })).toBeVisible();

  const seen: string[] = [];
  let sawOrganisation = false;
  let reachedMain = false;

  for (let i = 0; i < 40 && !reachedMain; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      const w = window as unknown as { __lastFocused?: Element | null };
      const stuck = el !== null && el !== document.body && w.__lastFocused === el;
      w.__lastFocused = el;
      return {
        stuck,
        label:
          el && el !== document.body
            ? `${el.tagName}:${el.getAttribute("aria-label") ?? el.textContent?.trim().slice(0, 40) ?? ""}`
            : "body",
        inMain: !!el && el !== document.body && !el.closest("aside"),
      };
    });
    expect(info.stuck, `Tab press ${i + 1} left focus stuck on ${info.label}`).toBe(false);
    seen.push(info.label);
    if (/your organisation/i.test(info.label)) sawOrganisation = true;
    if (sawOrganisation && info.inMain) reachedMain = true;
  }

  expect(sawOrganisation, `never reached "Your organisation"; saw: ${seen.join(" → ")}`).toBe(true);
  expect(
    reachedMain,
    `focus never progressed past the sidebar into main content; saw: ${seen.join(" → ")}`
  ).toBe(true);
});

test("the authenticated shell has no serious automated accessibility defects", async ({ page }) => {
  await page.goto("/app");
  await expect(page.getByRole("link", { name: /your organisation —/i })).toBeVisible();
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(
    violations.filter((v) => v.impact === "serious" || v.impact === "critical"),
  ).toEqual([]);
});
