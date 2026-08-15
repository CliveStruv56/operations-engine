import { defineConfig } from "@playwright/test";

// E2E runs against a dev server on its own port with a fully mocked backend:
// the specs intercept every /api/v1 and Supabase auth request, so no database,
// API process, or real login is needed. Dummy env values below exist only so
// the Supabase browser client can construct itself.
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://localhost:3100",
    viewport: { width: 1280, height: 720 },
  },
  webServer: {
    command: "pnpm dev --port 3100",
    url: "http://localhost:3100",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      NEXT_PUBLIC_SUPABASE_URL: "http://localhost:9999",
      NEXT_PUBLIC_SUPABASE_ANON_KEY: "e2e-anon-key",
      NEXT_PUBLIC_API_URL: "http://localhost:9998",
      // Skips the server-side auth guard in proxy.ts — e2e only.
      E2E_AUTH_BYPASS: "1",
    },
  },
});
