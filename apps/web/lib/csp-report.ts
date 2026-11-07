/** Turns browser CSP violation reports into short, safe log records
 * (app/api/csp-report/route.ts). Anyone can post to that endpoint, so only
 * known fields are kept, each is clipped, and URLs lose their query strings
 * — a presigned storage URL carries its signature there. */

const MAX_REPORTS = 5;

type Report = Record<string, unknown>;

function clip(value: unknown, max = 200): string | undefined {
  if (typeof value !== "string" && typeof value !== "number") return undefined;
  return String(value).slice(0, max);
}

function stripQuery(value: unknown): string | undefined {
  const s = clip(value, 400);
  if (!s) return s;
  return s.replace(/[?#].*$/, "").slice(0, 200);
}

/** Both report shapes: report-uri's {"csp-report": {...}} with kebab-case
 * keys, and the Reporting API's [{type, body: {...}}] with camelCase. */
export function summarise(payload: unknown): Report[] {
  const raw: Report[] = Array.isArray(payload)
    ? payload
        .filter((r): r is Report => typeof r === "object" && r !== null)
        .map((r) => (r.body ?? {}) as Report)
    : typeof payload === "object" && payload !== null && "csp-report" in payload
      ? [(payload as Report)["csp-report"] as Report]
      : [];
  return raw.slice(0, MAX_REPORTS).map((r) => ({
    directive: clip(r["effective-directive"] ?? r.effectiveDirective ?? r["violated-directive"], 60),
    blocked: stripQuery(r["blocked-uri"] ?? r.blockedURL),
    page: stripQuery(r["document-uri"] ?? r.documentURL),
    source: stripQuery(r["source-file"] ?? r.sourceFile),
    line: clip(r["line-number"] ?? r.lineNumber, 10),
    disposition: clip(r.disposition, 10),
    sample: clip(r["script-sample"] ?? r.sample, 80),
  }));
}
