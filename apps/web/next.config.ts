import type { NextConfig } from "next";
import { BASELINE_POLICY } from "./lib/csp";

// Response headers for every route (code review WEB-1). `/app` is fully
// client-rendered with the session in cookies, so framing and MIME sniffing
// are the cheap wins.
//
// Content-Security-Policy: pages get theirs from proxy.ts with a per-request
// nonce (lib/csp.ts). A CSP header from here on a page would reach the
// renderer as the request's CSP and strip the nonce from every script, so
// only API routes, which the proxy never sees, get the baseline from here.
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
        source: "/api/:path*",
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
