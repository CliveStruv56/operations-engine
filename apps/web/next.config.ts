import type { NextConfig } from "next";

// Response headers for every route (code review WEB-1). `/app` is fully
// client-rendered with the session in cookies, so framing and MIME sniffing
// are the cheap wins. The CSP carries only directives that cannot break the
// app: a script-src policy needs a per-request nonce for Next's inline
// bootstrap scripts, plus connect-src entries for the API, Supabase and the
// R2 bucket — that is a follow-up to land with an e2e run, not a guess here.
const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: "frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'",
  },
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
    return [{ source: "/:path*", headers: securityHeaders }];
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
