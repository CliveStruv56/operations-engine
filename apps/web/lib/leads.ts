/* Server-only module — import it only from route handlers.
 *
 * Lead delivery adapter. The public site stores no lead data itself: each
 * validated submission is handed to exactly one adapter. Swap the adapter
 * for the chosen CRM/email destination without touching the route handler. */

export interface LeadRecord {
  kind: "demo" | "pilot";
  email: string;
  workflow: string;
  name?: string;
  organisation?: string;
  teamSize?: string;
  need?: string;
  sourcePage?: string;
  utm?: Record<string, string>;
  consentVersion: string;
  submittedAt: string;
  idempotencyKey: string;
}

export interface LeadAdapter {
  deliver(lead: LeadRecord): Promise<void>;
}

/* Default adapter: POST to LEAD_WEBHOOK_URL (e.g. a CRM inbound webhook or
 * an email relay). Falls back to server logs in local dev so the flow is
 * testable before a destination is chosen. */
const webhookAdapter: LeadAdapter = {
  async deliver(lead) {
    const url = process.env.LEAD_WEBHOOK_URL;
    if (!url) {
      console.info("[leads] no LEAD_WEBHOOK_URL configured; lead:", {
        ...lead,
        // Keep full details out of shared logs.
        email: lead.email.replace(/(.).*(@.*)/, "$1***$2"),
        need: lead.need ? `${lead.need.length} chars` : undefined,
      });
      return;
    }
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(lead),
    });
    if (!res.ok) {
      throw new Error(`Lead webhook responded ${res.status}`);
    }
  },
};

export function getLeadAdapter(): LeadAdapter {
  return webhookAdapter;
}
