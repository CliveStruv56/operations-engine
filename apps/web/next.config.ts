import type { NextConfig } from "next";
import { BASELINE_POLICY, cspEnforced } from "./lib/csp";

// Response headers for every route (code review WEB-1). `/app` is fully
// client-rendered with the session in cookies, so framing and MIME sniffing
// are the cheap wins.
//
// Content-Security-Policy: pages get the full nonce policy from proxy.ts
// (lib/csp.ts). While that runs report-only, the 12 Oct baseline is enforced
// here on every route; once CSP_ENFORCE=1, pages get only the proxy's policy
// (which includes the baseline) and the baseline stays on API routes, which
// the proxy never sees. One enforced CSP header per response either way.
const securityHeaders = [
  // frame-ancestors' predecessor, for browsers that predate it.
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  // No includeSubDomains: other hosts under the apex are not ours to commit.
  { key: "Strict-Transport-Security", value: "max-age=31536000" },
];

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image (apps/web/Dockerfile).
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders },
      {
        source: cspEnforced() ? "/api/:path*" : "/:path*",
        headers: [{ key: "Content-Security-Policy", value: BASELINE_POLICY }],
      },
    ];
  },
  async redirects() {
    return [
      // The pre-custom-domain host still resolves, and auth cookies are
      // host-scoped — a stale bookmark there is a guaranteed "logged out".
      // One permanent redirect retires it everywhere at once.
      {
        source: "/:path*",
        has: [{ type: "host", value: "ops-engine-staging-web.vercel.app" }],
        destination: "https://www.flowgridos.co.uk/:path*",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
