"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { safeNext, withNext } from "@/lib/auth-redirect";
import { Button, ErrorNote } from "@/components/ui";
import { input as inputCls } from "@/components/ui/styles";

export default function LoginPage() {
  return (
    // useSearchParams needs a Suspense boundary at the page level.
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const acceptingInvite = next.startsWith("/invite/");
  // Set by the auth callback when an email link could not finish on its own.
  const notice = params.get("notice");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    router.push(next);
    router.refresh();
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <p className="data mb-2 text-electric-blue uppercase">Flowgrid OS</p>
        <form
          onSubmit={onSubmit}
          className="space-y-4 rounded-card border border-edge bg-card p-6 shadow-card"
        >
          <h1 className="font-display text-hearth-page leading-tight font-medium tracking-[-0.01em]">
            Sign in
          </h1>
          {notice && (
            <p className="rounded-lg border border-edge bg-sidebar px-3 py-2 text-sm text-subtle">
              {notice}
            </p>
          )}
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
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`mt-1 font-normal ${inputCls}`}
            />
          </label>
          {error && <ErrorNote>{error}</ErrorNote>}
          <Button
            type="submit"
            loading={busy}
            loadingLabel="Signing in…"
            className="w-full"
          >
            Sign in
          </Button>
          {acceptingInvite ? (
            <p className="text-sm text-subtle">
              New to Flowgrid?{" "}
              <Link href={withNext("/signup", next)} className="underline hover:text-ink">
                Create the account for your invited email
              </Link>
              .
            </p>
          ) : (
            <p className="text-sm text-subtle">
              Need access? Flowgrid workspaces are invitation-only.{" "}
              <Link href="/contact" className="underline hover:text-ink">
                Book a demo
              </Link>
              .
            </p>
          )}
          <Link href="/" className="inline-block text-sm text-subtle underline hover:text-ink">
            Back to the Flowgrid website
          </Link>
        </form>
      </div>
    </main>
  );
}
