"use client";

import { useMemo, useState } from "react";
import { submitLead, WORKFLOW_OPTIONS } from "./lead-client";

export function PilotForm() {
  const idempotencyKey = useMemo(() => crypto.randomUUID(), []);
  const [email, setEmail] = useState("");
  const [workflow, setWorkflow] = useState("not-sure");
  const [company, setCompany] = useState(""); // honeypot
  const [status, setStatus] = useState<"idle" | "busy" | "done" | "error">(
    "idle",
  );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (status === "busy" || status === "done") return;
    setStatus("busy");
    const ok = await submitLead({
      kind: "pilot",
      email,
      workflow,
      website: company,
      idempotencyKey,
    });
    setStatus(ok ? "done" : "error");
  }

  if (status === "done") {
    return (
      <p role="status" className="text-[16px] text-ink">
        You&rsquo;re on the list — we&rsquo;ll email you about the pilot. We
        write rarely, and you can unsubscribe at any time.
      </p>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex max-w-xl flex-col gap-3 sm:flex-row sm:items-end">
      <div className="flex-1">
        <label
          htmlFor="pilot-email"
          className="block text-[12px] font-medium uppercase tracking-[0.08em] text-slate"
        >
          Work email
        </label>
        <input
          id="pilot-email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-2 w-full rounded-lg border border-edge-input bg-canvas px-4 py-3 text-[16px] text-ink placeholder:text-faint"
          placeholder="you@organisation.org.uk"
        />
      </div>
      <div>
        <label
          htmlFor="pilot-workflow"
          className="block text-[12px] font-medium uppercase tracking-[0.08em] text-slate"
        >
          Interested in
        </label>
        <select
          id="pilot-workflow"
          value={workflow}
          onChange={(e) => setWorkflow(e.target.value)}
          className="mt-2 w-full rounded-lg border border-edge-input bg-canvas px-4 py-3 text-[16px] text-ink sm:w-auto"
        >
          {WORKFLOW_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      {/* Honeypot — hidden from everyone, including assistive tech. */}
      <div aria-hidden className="hidden">
        <label htmlFor="pilot-website">Website</label>
        <input
          id="pilot-website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
        />
      </div>
      <button
        type="submit"
        disabled={status === "busy"}
        className="inline-flex min-h-[50px] items-center justify-center rounded-full bg-accent px-6 py-3 text-[16px] font-medium text-accent-ink transition-colors hover:bg-accent-deep disabled:opacity-60"
      >
        {status === "busy" ? "Joining…" : "Join the pilot list"}
      </button>
      {status === "error" && (
        <p role="alert" className="text-[14px] text-danger sm:basis-full">
          That didn&rsquo;t go through — please try again, or email{" "}
          <a href="mailto:hello@flowgridos.co.uk" className="underline">
            hello@flowgridos.co.uk
          </a>
          .
        </p>
      )}
    </form>
  );
}
