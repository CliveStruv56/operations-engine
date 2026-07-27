"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { api } from "@/lib/api";

export default function InvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const router = useRouter();
  const [status, setStatus] = useState("Checking invite…");

  useEffect(() => {
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        router.push(`/signup?next=/invite/${token}`);
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
        setStatus(e instanceof Error ? e.message : "Invite is invalid or expired");
      }
    })();
  }, [token, router]);

  return <main className="p-8 text-neutral-600">{status}</main>;
}
