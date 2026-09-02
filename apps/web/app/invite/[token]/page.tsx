"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { api, ApiError } from "@/lib/api";
import { withNext } from "@/lib/auth-redirect";
import { Button } from "@/components/ui";

type Mismatch = { invited: string; signedInAs: string };

export default function InvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const router = useRouter();
  const invitePath = `/invite/${token}`;
  const [status, setStatus] = useState("Checking invite…");
  const [mismatch, setMismatch] = useState<Mismatch | null>(null);

  useEffect(() => {
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        // Newcomers sign up; the return path brings them back here once
        // their email is confirmed. The signup page links to login for
        // people who already have an account.
        router.push(withNext("/signup", invitePath));
        return;
      }
      try {
        const res = await api<{ tenant_id: string }>("/invites/accept", {
          method: "POST",
          body: JSON.stringify({ token }),
        });
        localStorage.setItem("tenantId", res.tenant_id);
        router.push("/app");
      } catch (e) {
        if (e instanceof ApiError && e.code === "invite_email_mismatch") {
          const p = (e.payload ?? {}) as { invited_email?: string; signed_in_email?: string };
          setMismatch({
            invited: p.invited_email ?? "another address",
            signedInAs: p.signed_in_email ?? session.user.email ?? "this account",
          });
          return;
        }
        setStatus(e instanceof Error ? e.message : "Invite is invalid or expired");
      }
    })();
  }, [token, invitePath, router]);

  async function switchAccount() {
    await createClient().auth.signOut();
    router.push(withNext("/login", invitePath));
  }

  if (mismatch) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-4 rounded-card border border-edge bg-card p-6 shadow-card">
          <h1 className="font-display text-hearth-page leading-tight font-medium tracking-[-0.01em]">
            This invite is for someone else
          </h1>
          <p className="text-sm text-subtle">
            It was sent to <span className="font-semibold text-ink">{mismatch.invited}</span>, but
            you are signed in as{" "}
            <span className="font-semibold text-ink">{mismatch.signedInAs}</span>. Sign out and
            continue as the invited address to join the workspace.
          </p>
          <Button type="button" onClick={switchAccount} className="w-full">
            Sign out and continue as {mismatch.invited}
          </Button>
          <p className="text-sm text-subtle">
            Wrong address on the invite? Ask whoever sent it to reissue it to you.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <p className="data text-ink-muted">{status}</p>
    </main>
  );
}
