import { NextRequest, NextResponse } from "next/server";
import { getLeadAdapter, type LeadRecord } from "@/lib/leads";

/* Public lead endpoint for the marketing site's demo and pilot forms.
 * Validates server-side, rate-limits per IP, dedupes on Idempotency-Key
 * and hands off to the configured adapter. No lead data is stored here. */

export const runtime = "nodejs";

const CONSENT_VERSION = "2026-08-16";
const WORKFLOWS = new Set([
  "core",
  "development-projects",
  "grants",
  "not-sure",
]);
const TEAM_SIZES = new Set(["1-4", "5-14", "15-49", "50+"]);
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/* In-memory guards. Fine for a single long-lived instance (Railway); a
 * multi-instance/serverless deploy should move these to Redis. */
const seenKeys = new Map<string, number>();
const hits = new Map<string, { count: number; windowStart: number }>();
const RATE_LIMIT = 5;
const RATE_WINDOW_MS = 60_000;
const KEY_TTL_MS = 60 * 60_000;

function rateLimited(ip: string): boolean {
  const now = Date.now();
  const entry = hits.get(ip);
  if (!entry || now - entry.windowStart > RATE_WINDOW_MS) {
    hits.set(ip, { count: 1, windowStart: now });
    return false;
  }
  entry.count += 1;
  return entry.count > RATE_LIMIT;
}

function alreadySeen(key: string): boolean {
  const now = Date.now();
  for (const [k, at] of seenKeys) {
    if (now - at > KEY_TTL_MS) seenKeys.delete(k);
  }
  if (seenKeys.has(key)) return true;
  seenKeys.set(key, now);
  return false;
}

function str(value: unknown, max: number): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, max) : undefined;
}

export async function POST(request: NextRequest) {
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "local";
  if (rateLimited(ip)) {
    return NextResponse.json(
      { error: "Too many requests. Please try again in a minute." },
      { status: 429 },
    );
  }

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request." }, { status: 400 });
  }

  // Honeypot: pretend success so bots learn nothing.
  if (str(body.website, 200)) {
    return NextResponse.json({ ok: true }, { status: 202 });
  }

  const kind = body.kind === "demo" || body.kind === "pilot" ? body.kind : null;
  const email = str(body.email, 320);
  const workflow = str(body.workflow, 40);

  const errors: Record<string, string> = {};
  if (!kind) errors.kind = "Unknown request type.";
  if (!email || !EMAIL_RE.test(email)) {
    errors.email = "Enter a valid work email address.";
  }
  if (!workflow || !WORKFLOWS.has(workflow)) {
    errors.workflow = "Choose a workflow.";
  }

  const name = str(body.name, 200);
  const organisation = str(body.organisation, 200);
  if (kind === "demo") {
    if (!name) errors.name = "Enter your name.";
    if (!organisation) errors.organisation = "Enter your organisation.";
  }
  const teamSize = str(body.teamSize, 10);
  if (teamSize && !TEAM_SIZES.has(teamSize)) {
    errors.teamSize = "Choose a team size.";
  }

  if (Object.keys(errors).length > 0) {
    return NextResponse.json({ error: "Validation failed", errors }, { status: 422 });
  }

  const idempotencyKey =
    str(request.headers.get("idempotency-key"), 100) ?? crypto.randomUUID();
  if (alreadySeen(`${idempotencyKey}:${email}`)) {
    return NextResponse.json({ ok: true, duplicate: true });
  }

  const utmRaw = body.utm;
  const utm: Record<string, string> = {};
  if (utmRaw && typeof utmRaw === "object") {
    for (const key of ["utm_source", "utm_medium", "utm_campaign"]) {
      const value = str((utmRaw as Record<string, unknown>)[key], 200);
      if (value) utm[key] = value;
    }
  }

  const lead: LeadRecord = {
    kind: kind!,
    email: email!,
    workflow: workflow!,
    name,
    organisation,
    teamSize,
    need: str(body.need, 500),
    sourcePage: str(body.sourcePage, 200),
    utm,
    consentVersion: CONSENT_VERSION,
    submittedAt: new Date().toISOString(),
    idempotencyKey,
  };

  try {
    await getLeadAdapter().deliver(lead);
  } catch (err) {
    console.error("[leads] delivery failed", err);
    return NextResponse.json(
      {
        error:
          "We couldn't record your request. Please retry, or email hello@flowgridos.co.uk.",
      },
      { status: 502 },
    );
  }

  return NextResponse.json({ ok: true });
}
