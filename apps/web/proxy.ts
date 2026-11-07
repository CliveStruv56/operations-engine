import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { safeNext } from "@/lib/auth-redirect";
import {
  buildCsp,
  cspEnforced,
  cspResponseHeader,
  makeNonce,
  originsFromEnv,
} from "@/lib/csp";

// Two jobs: a per-request Content-Security-Policy nonce on every page
// (lib/csp.ts), and the auth guard on /app, /login and /signup.
export async function proxy(request: NextRequest) {
  const nonce = makeNonce();
  const policy = buildCsp(nonce, originsFromEnv(), {
    dev: process.env.NODE_ENV === "development",
  });
  // Next reads the nonce from this request header while it renders, and
  // stamps it on its own scripts. Request-side only: the browser gets the
  // response headers set at the bottom.
  const forward = () => {
    const headers = new Headers(request.headers);
    headers.set("content-security-policy", policy);
    headers.set("x-nonce", nonce);
    return NextResponse.next({ request: { headers } });
  };
  const finish = (response: NextResponse) => {
    response.headers.set(...cspResponseHeader(policy, cspEnforced()));
    return response;
  };

  const path = request.nextUrl.pathname;
  const guarded =
    path === "/app" || path.startsWith("/app/") || path === "/login" || path === "/signup";
  // Playwright-only escape hatch: the e2e suite mocks every API and auth
  // request in the browser, but this guard runs in the Next server process
  // where those mocks cannot reach. Server-side env var, never NEXT_PUBLIC —
  // it must not be settable from a client, and must never be set in a real
  // deployment (see playwright.config.ts, the only place that sets it).
  if (!guarded || process.env.E2E_AUTH_BYPASS === "1") return finish(forward());

  let response = forward();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          response = forward();
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user && path.startsWith("/app")) {
    // Remember where they were heading so signing in lands them back there.
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    const wanted = request.nextUrl.pathname + request.nextUrl.search;
    if (wanted !== "/app") url.searchParams.set("next", wanted);
    return NextResponse.redirect(url);
  }
  // The mirror rule: a signed-in visitor shown the login form reads it as
  // "you were logged out" and retypes credentials that were never lost.
  // An invite sends newcomers to signup with `next` set — a visitor who is
  // already signed in goes straight on to it instead of losing the invite.
  if (user && (path.startsWith("/login") || path.startsWith("/signup"))) {
    const url = request.nextUrl.clone();
    url.search = "";
    url.pathname = safeNext(request.nextUrl.searchParams.get("next"));
    return NextResponse.redirect(url);
  }
  return finish(response);
}

export const config = {
  matcher: [
    // The auth guard: always, prefetches included.
    "/app/:path*",
    "/login",
    "/signup",
    // The CSP: every page. Not API routes, build output, image optimisation,
    // files with an extension (public/, robots.txt, sitemap.xml), or router
    // prefetches — none of those is an HTML document.
    {
      source: "/((?!api/|_next/static|_next/image|favicon\\.ico|.*\\.[a-zA-Z0-9]+$).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
