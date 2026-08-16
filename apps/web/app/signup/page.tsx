"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { Button, ErrorNote } from "@/components/ui";
import { input as inputCls } from "@/components/ui/styles";

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
        <p className="data mb-2 text-electric-blue uppercase">Flowgrid</p>
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
            <Link href="/login" className="underline hover:text-ink">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
