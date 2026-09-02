"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { safeNext, withNext } from "@/lib/auth-redirect";
import { Button, ErrorNote } from "@/components/ui";
import { input as inputCls } from "@/components/ui/styles";

export default function SignupPage() {
  return (
    // useSearchParams needs a Suspense boundary at the page level.
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}

function SignupForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const acceptingInvite = next.startsWith("/invite/");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const supabase = createClient();
    // Confirm-email links come back to the environment the person signed up
    // from, via the auth callback that turns the one-time code into a session
    // and then carries on to `next` (an invite, usually). The Supabase
    // project's redirect allow-list must include this origin or Supabase
    // falls back to its Site URL — see docs/staging-deploy-checklist.md.
    const callback = new URL("/auth/callback", window.location.origin);
    if (next !== "/app") callback.searchParams.set("next", next);
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: callback.toString() },
    });
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    if (data.session) {
      // Email confirmation is off for this project: signed in already.
      router.push(next);
      router.refresh();
      return;
    }
    setSentTo(email);
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <p className="data mb-2 text-electric-blue uppercase">Flowgrid OS</p>
        {!acceptingInvite ? (
          <section className="space-y-4 rounded-card border border-edge bg-card p-6 shadow-card">
            <h1 className="font-display text-hearth-page leading-tight font-medium tracking-[-0.01em]">
              Account creation is by invitation
            </h1>
            <p className="text-sm leading-relaxed text-subtle">
              Flowgrid sets up each workspace with the organisation taking part
              in a pilot. If you received an invitation, open the link in that
              email to create your account.
            </p>
            <Link
              href="/contact"
              className="inline-flex rounded-btn bg-accent px-5 py-2.5 text-sm font-medium text-accent-ink hover:bg-accent-deep"
            >
              Book a demo
            </Link>
            <div>
              <Link href="/login" className="text-sm text-subtle underline hover:text-ink">
                Already have an account? Sign in
              </Link>
            </div>
            <Link href="/" className="inline-block text-sm text-subtle underline hover:text-ink">
              Back to the Flowgrid website
            </Link>
          </section>
        ) : sentTo ? (
          <div className="space-y-4 rounded-card border border-edge bg-card p-6 shadow-card">
            <h1 className="font-display text-hearth-page leading-tight font-medium tracking-[-0.01em]">
              Check your email
            </h1>
            <p className="text-sm text-subtle">
              We sent a confirmation link to <span className="font-semibold text-ink">{sentTo}</span>.
              Open it on this device to finish creating your account
              {next.startsWith("/invite/") ? " and join the workspace you were invited to" : ""}.
            </p>
            <p className="text-sm text-subtle">
              Nothing arrived? Check your spam folder, or{" "}
              <button
                type="button"
                onClick={() => setSentTo(null)}
                className="underline hover:text-ink"
              >
                try again
              </button>
              .
            </p>
          </div>
        ) : (
          <form
            onSubmit={onSubmit}
            className="space-y-4 rounded-card border border-edge bg-card p-6 shadow-card"
          >
            <h1 className="font-display text-hearth-page leading-tight font-medium tracking-[-0.01em]">
              Create account
            </h1>
            <label className="block text-sm font-semibold">
              Email
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={`mt-1 font-normal ${inputCls}`}
              />
            </label>
            <label className="block text-sm font-semibold">
              Password
              <span className="mt-0.5 block text-xs font-normal text-subtle">
                At least 8 characters.
              </span>
              <input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`mt-1 font-normal ${inputCls}`}
              />
            </label>
            {error && <ErrorNote>{error}</ErrorNote>}
            <Button type="submit" loading={busy} loadingLabel="Creating…" className="w-full">
              Sign up
            </Button>
            <p className="text-sm text-subtle">
              Have an account?{" "}
              <Link href={withNext("/login", next)} className="underline hover:text-ink">
                Sign in
              </Link>
            </p>
          </form>
        )}
      </div>
    </main>
  );
}
