/* Client helper shared by the demo and pilot forms. Collects the source
 * page and UTM values (stored server-side, never sent to analytics). */

export { WORKFLOW_OPTIONS } from "@/lib/product-language";

export interface LeadInput {
  kind: "demo" | "pilot";
  email: string;
  workflow: string;
  name?: string;
  organisation?: string;
  teamSize?: string;
  need?: string;
  /** Honeypot field — must be empty for real submissions. */
  website?: string;
  idempotencyKey: string;
}

export async function submitLead(input: LeadInput): Promise<boolean> {
  const params = new URLSearchParams(window.location.search);
  const utm: Record<string, string> = {};
  for (const key of ["utm_source", "utm_medium", "utm_campaign"]) {
    const value = params.get(key);
    if (value) utm[key] = value.slice(0, 200);
  }
  try {
    const res = await fetch("/api/leads", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": input.idempotencyKey,
      },
      body: JSON.stringify({
        ...input,
        sourcePage: window.location.pathname,
        utm,
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
