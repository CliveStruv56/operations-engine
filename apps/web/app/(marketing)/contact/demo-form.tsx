"use client";

import { useMemo, useState } from "react";
import { submitLead, WORKFLOW_OPTIONS } from "../lead-client";

const TEAM_SIZES = ["1-4", "5-14", "15-49", "50+"];

const inputCls =
  "mt-2 w-full rounded-lg border border-edge-input bg-canvas px-4 py-3 text-[16px] text-ink placeholder:text-faint";
const labelCls =
  "block text-[12px] font-medium uppercase tracking-[0.08em] text-slate";

export function DemoForm() {
  const idempotencyKey = useMemo(() => crypto.randomUUID(), []);
  const [form, setForm] = useState({
    email: "",
    name: "",
    organisation: "",
    workflow: "not-sure",
    teamSize: "",
    need: "",
    website: "", // honeypot
  });
  const [status, setStatus] = useState<"idle" | "busy" | "done" | "error">(
    "idle",
  );

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (status === "busy" || status === "done") return;
    setStatus("busy");
    const ok = await submitLead({
      kind: "demo",
      email: form.email,
      name: form.name,
      organisation: form.organisation,
      workflow: form.workflow,
      teamSize: form.teamSize || undefined,
      need: form.need || undefined,
      website: form.website,
      idempotencyKey,
    });
    setStatus(ok ? "done" : "error");
  }

  if (status === "done") {
    return (
      <div role="status" className="rounded-lg border border-stone bg-pale-sage p-6">
        <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
          Request received
        </p>
        <p className="mt-2 text-[18px] leading-[1.42] text-ink">
          Thank you — we&rsquo;ll reply by email within two working days to
          arrange a time. You&rsquo;ll get a short confirmation email with
          next steps now.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate={false} className="flex flex-col gap-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="demo-name" className={labelCls}>
            Name
          </label>
          <input
            id="demo-name"
            required
            autoComplete="name"
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label htmlFor="demo-email" className={labelCls}>
            Work email
          </label>
          <input
            id="demo-email"
            type="email"
            required
            autoComplete="email"
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
            className={inputCls}
          />
        </div>
      </div>
      <div>
        <label htmlFor="demo-org" className={labelCls}>
          Organisation
        </label>
        <input
          id="demo-org"
          required
          autoComplete="organization"
          value={form.organisation}
          onChange={(e) => set("organisation", e.target.value)}
          className={inputCls}
        />
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="demo-workflow" className={labelCls}>
            Which workflow?
          </label>
          <select
            id="demo-workflow"
            required
            value={form.workflow}
            onChange={(e) => set("workflow", e.target.value)}
            className={inputCls}
          >
            {WORKFLOW_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="demo-team" className={labelCls}>
            Team size <span className="normal-case text-faint">(optional)</span>
          </label>
          <select
            id="demo-team"
            value={form.teamSize}
            onChange={(e) => set("teamSize", e.target.value)}
            className={inputCls}
          >
            <option value="">Prefer not to say</option>
            {TEAM_SIZES.map((s) => (
              <option key={s} value={s}>
                {s} people
              </option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label htmlFor="demo-need" className={labelCls}>
          What do you repeatedly need to find, check or produce?{" "}
          <span className="normal-case text-faint">(optional)</span>
        </label>
        <textarea
          id="demo-need"
          rows={4}
          maxLength={500}
          value={form.need}
          onChange={(e) => set("need", e.target.value)}
          className={inputCls}
          aria-describedby="demo-need-hint"
        />
        <p id="demo-need-hint" className="mt-1.5 text-[13px] text-faint">
          Up to 500 characters. Please don&rsquo;t include sensitive personal
          data.
        </p>
      </div>
      {/* Honeypot — hidden from everyone, including assistive tech. */}
      <div aria-hidden className="hidden">
        <label htmlFor="demo-website">Website</label>
        <input
          id="demo-website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={form.website}
          onChange={(e) => set("website", e.target.value)}
        />
      </div>
      <p className="text-[14px] leading-[1.5] text-slate">
        We use these details only to respond to your enquiry — see the{" "}
        <a href="/privacy" className="text-deep-violet underline-offset-4 hover:underline">
          privacy notice
        </a>
        . No marketing list unless you separately opt in.
      </p>
      <div>
        <button
          type="submit"
          disabled={status === "busy"}
          className="inline-flex min-h-[50px] items-center justify-center rounded-full bg-accent px-8 py-3 text-[16px] font-medium text-accent-ink transition-colors hover:bg-accent-deep disabled:opacity-60"
        >
          {status === "busy" ? "Sending…" : "Request a demo"}
        </button>
      </div>
      {status === "error" && (
        <p role="alert" className="text-[14px] text-danger">
          Your request didn&rsquo;t go through. Please try again, or email{" "}
          <a href="mailto:hello@flowgridos.co.uk" className="underline">
            hello@flowgridos.co.uk
          </a>{" "}
          and we&rsquo;ll pick it up directly.
        </p>
      )}
    </form>
  );
}
