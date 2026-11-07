import { defineConfig } from "@playwright/test";

// E2E runs against a dev server on its own port with a fully mocked backend:
// the specs intercept every /api/v1 and Supabase auth request, so no database,
// API process, or real login is needed. Dummy env values below exist only so
// the Supabase browser client can construct itself.
//
// E2E_PROD=1 runs against a production build instead (`next build` then
// `next start`, on its own port) — CI does this for e2e/csp.spec.ts, since
// only a production build shows whether every page gets its CSP nonce.
const prod = process.env.E2E_PROD === "1";
const port = prod ? 3101 : 3100;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: `http://localhost:${port}`,
    viewport: { width: 1280, height: 720 },
  },
  webServer: {
    command: prod ? `pnpm build && pnpm start --port ${port}` : `pnpm dev --port ${port}`,
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: prod ? 400_000 : 180_000,
    env: {
      NEXT_PUBLIC_SUPABASE_URL: "http://localhost:9999",
      NEXT_PUBLIC_SUPABASE_ANON_KEY: "e2e-anon-key",
      NEXT_PUBLIC_API_URL: "http://localhost:9998",
      // Presigned upload and logo URLs point here; the specs mock it.
      NEXT_PUBLIC_STORAGE_ORIGIN: "http://localhost:9997",
      // Every e2e run enforces the Content-Security-Policy (production
      // deploys default to report-only), so a refused script or request
      // breaks the specs that need it, not just e2e/csp.spec.ts.
      CSP_ENFORCE: "1",
      // Skips the server-side auth guard in proxy.ts — e2e only.
      E2E_AUTH_BYPASS: "1",
    },
  },
});
