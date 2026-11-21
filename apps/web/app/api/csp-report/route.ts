import { NextRequest } from "next/server";
import { summarise } from "@/lib/csp-report";

/* Browsers POST Content-Security-Policy violations here (the policy's
 * report-uri, lib/csp.ts). Each one becomes a single log line, so the
 * report-only policy can be watched in the host's logs before it is
 * enforced. Nothing is stored; the body is capped and lib/csp-report.ts
 * keeps only known, clipped fields. */

export const runtime = "nodejs";

const MAX_BODY = 16_000;

export async function POST(request: NextRequest) {
  const text = (await request.text().catch(() => "")).slice(0, MAX_BODY);
  let payload: unknown = null;
  try {
    payload = JSON.parse(text);
  } catch {
    return new Response(null, { status: 204 });
  }
  for (const report of summarise(payload)) {
    console.warn(`csp-violation ${JSON.stringify(report)}`);
  }
  return new Response(null, { status: 204 });
}
