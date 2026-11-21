import { mkdirSync, writeFileSync } from "node:fs";
import { test } from "@playwright/test";
import { SCREENS, mockBackend } from "./mock-backend";

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
      await mockBackend(page, (path) => missing.add(path));

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
  await mockBackend(page);
  await page.goto("/app");
  await page.waitForLoadState("networkidle");
  const toggle = page.getByRole("button", { name: /menu|navigation|open/i }).first();
  if (await toggle.isVisible()) await toggle.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/phone/drawer-open.png` });
});
