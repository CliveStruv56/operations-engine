"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const supabase = createClient();
    // Confirm-email links follow the environment the user signed up from —
    // the Supabase project's site_url points at dev, which would otherwise
    // bounce staging/production signups to localhost.
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/app` },
    });
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    router.push("/app");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <p className="data mb-2 text-ink-faint uppercase">Operations Engine</p>
        <form
          onSubmit={onSubmit}
          className="space-y-4 rounded-card border border-edge bg-surface p-6 shadow-sm"
        >
          <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">Create account</h1>
          <label className="block text-sm font-semibold">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line px-3 py-2 text-sm font-normal"
            />
          </label>
          <label className="block text-sm font-semibold">
            Password
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              placeholder="8+ characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-[10px] border border-line px-3 py-2 text-sm font-normal"
            />
          </label>
          {error && (
            <p className="rounded-[10px] bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-[10px] bg-accent px-3 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50"
          >
            {busy ? "Creating…" : "Sign up"}
          </button>
          <p className="text-sm text-ink-muted">
            Have an account?{" "}
            <Link href="/login" className="underline hover:text-ink">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
