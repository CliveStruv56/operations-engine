import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { safeNext, withNext } from "@/lib/auth-redirect";

/** Where Supabase sends the browser after an email link is verified.
 *
 * The confirmation email carries a one-time code; exchanging it here, on the
 * server, sets the session cookies before the person reaches a guarded page.
 * Landing them straight on `/app` used to lose the code: proxy.ts saw no
 * cookie and bounced to the login form before the browser could act.
 *
 * Supabase reports link failures (expired, already used) as query params on
 * this same URL, so those are turned into a readable notice on the login page
 * rather than a bare error string. */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const next = safeNext(searchParams.get("next"));
  const code = searchParams.get("code");
  const linkError = searchParams.get("error_description") ?? searchParams.get("error");

  if (linkError || !code) {
    const login = new URL(withNext("/login", next), origin);
    login.searchParams.set(
      "notice",
      linkError
        ? "That email link has expired or was already used. Sign in, or sign up again for a fresh link."
        : "Sign in to continue."
    );
    return NextResponse.redirect(login);
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    // The email itself is confirmed at Supabase before we get here; the
    // exchange fails when the link was opened in a different browser from
    // the one that signed up (the PKCE verifier lives in that browser).
    const login = new URL(withNext("/login", next), origin);
    login.searchParams.set("notice", "Your email is confirmed. Sign in to continue.");
    return NextResponse.redirect(login);
  }
  return NextResponse.redirect(new URL(next, origin));
}
