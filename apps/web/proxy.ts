import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { safeNext } from "@/lib/auth-redirect";

export async function proxy(request: NextRequest) {
  // Playwright-only escape hatch: the e2e suite mocks every API and auth
  // request in the browser, but this guard runs in the Next server process
  // where those mocks cannot reach. Server-side env var, never NEXT_PUBLIC —
  // it must not be settable from a client, and must never be set in a real
  // deployment (see playwright.config.ts, the only place that sets it).
  if (process.env.E2E_AUTH_BYPASS === "1") return NextResponse.next({ request });
  let response = NextResponse.next({ request });
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
          response = NextResponse.next({ request });
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

  const path = request.nextUrl.pathname;
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
  return response;
}

export const config = {
  matcher: ["/app/:path*", "/login", "/signup"],
};
