import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image (apps/web/Dockerfile).
  output: "standalone",
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
