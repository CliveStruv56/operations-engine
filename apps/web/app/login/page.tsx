"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
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
    const { error } = await supabase.auth.signInWithPassword({ email, password });
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
          <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">Sign in</h1>
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
              autoComplete="current-password"
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
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="text-sm text-ink-muted">
            No account?{" "}
            <Link href="/signup" className="underline hover:text-ink">
              Sign up
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
