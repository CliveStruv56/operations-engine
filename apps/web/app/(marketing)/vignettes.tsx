/* Composed, clearly-labelled representative product views, extending the
 * hero-visual technique (same frame, same honesty rule: example data only,
 * never customer information). Pastel stamps keep their fixed taxonomy —
 * sage = upcoming, lavender = in progress, rose = complete — and grounded
 * green stays scoped to trust states, --ok to RAG status. */

function Frame({
  ariaLabel,
  caption,
  children,
}: {
  ariaLabel: string;
  caption: string;
  children: React.ReactNode;
}) {
  return (
    <figure aria-label={ariaLabel}>
      <div className="rounded-[24px] border border-stone bg-canvas p-5">
        <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-slate">
          Representative product view — example data
        </p>
        {children}
      </div>
      <figcaption className="sr-only">{caption}</figcaption>
    </figure>
  );
}

export function ClaimsRegisterVignette() {
  const rows: {
    fact: string;
    source: string;
    pill: React.ReactNode;
  }[] = [
    {
      fact: "Registered charity · no. 1198765",
      source: "Charity Commission · imported 2 August 2026",
      pill: (
        <span className="inline-flex shrink-0 items-center rounded-full bg-grounded-tint px-3 py-1 text-[12px] font-medium text-grounded">
          Confirmed
        </span>
      ),
    },
    {
      fact: "Public liability insurance · £5m",
      source: "Policy schedule · renewed 3 March 2026",
      pill: (
        <span className="inline-flex shrink-0 items-center rounded-full bg-grounded-tint px-3 py-1 text-[12px] font-medium text-grounded">
          Confirmed
        </span>
      ),
    },
    {
      fact: "Safeguarding policy · v3.1",
      source: "Review due 12 September 2026",
      pill: (
        <span className="inline-flex shrink-0 items-center rounded-full border border-bone bg-band px-3 py-1 text-[12px] font-medium text-slate">
          Review due
        </span>
      ),
    },
    {
      fact: "2025 income · £412,000",
      source: "Proposed from the annual return — awaiting review",
      pill: (
        <span className="inline-flex shrink-0 items-center rounded-full border border-deep-violet px-3 py-1 text-[12px] font-medium text-deep-violet">
          Proposed
        </span>
      ),
    },
  ];
  return (
    <Frame
      ariaLabel="Representative claims register showing confirmed facts with their sources, one fact due for review and one imported proposal awaiting a person"
      caption="Illustration of the claims register: confirmed facts carry their source and date, a fact can fall due for review, and imported facts wait as proposals until someone confirms them."
    >
      <div className="mt-4 flex flex-col">
        {rows.map((row, i) => (
          <div
            key={row.fact}
            className={`flex items-center justify-between gap-3 py-3.5 ${i > 0 ? "border-t border-bone" : ""}`}
          >
            <div>
              <p className="text-[14px] text-ink">{row.fact}</p>
              <p className="mt-0.5 text-[12px] text-slate">{row.source}</p>
            </div>
            {row.pill}
          </div>
        ))}
      </div>
      <p className="mt-3 border-t border-bone pt-3 text-[12px] leading-[1.5] text-slate">
        Every draft draws on the confirmed version — nothing is asserted
        without a person confirming it.
      </p>
    </Frame>
  );
}

export function HealthCardVignette() {
  return (
    <Frame
      ariaLabel="Representative project health card showing the stage, RAG status, budget position and next milestone of an example project, exported as a branded PDF"
      caption="Illustration of a project health card: stage three of five in delivery, on track, budget committed against total, next milestone named — exported as a PDF in the client's branding."
    >
      <div className="mt-4 rounded-lg border border-bone p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
              Project health card · August 2026
            </p>
            <p className="mt-1 text-[16px] font-medium text-ink">
              Orchard Hall renewal
            </p>
          </div>
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-ok/10 px-3 py-1 text-[12px] font-medium text-ok">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-ok" />
            On track
          </span>
        </div>
        <dl className="mt-4 flex flex-col">
          <div className="flex items-center justify-between gap-3 border-t border-bone py-3">
            <dt className="text-[13px] text-slate">Stage</dt>
            <dd className="flex items-center gap-2.5 text-[14px] text-ink">
              3 of 5 · Delivery
              <span className="inline-flex items-center rounded-full bg-lavender-mist px-2.5 py-0.5 text-[11px] font-medium text-ink">
                In progress
              </span>
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-bone py-3">
            <dt className="text-[13px] text-slate">Budget committed</dt>
            <dd className="text-[14px] text-ink tabular-nums">
              £128,400 of £150,000
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-bone py-3">
            <dt className="text-[13px] text-slate">Next milestone</dt>
            <dd className="text-[14px] text-ink">
              Roof contract signed · 14 September
            </dd>
          </div>
        </dl>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3">
        <p className="text-[12px] leading-[1.5] text-slate">
          Assembled from the live project record.
        </p>
        <span className="inline-flex shrink-0 items-center rounded-full border border-burnt-amber px-3 py-1 text-[12px] font-medium text-burnt-amber">
          Export PDF
        </span>
      </div>
    </Frame>
  );
}

export function ReportingCalendarVignette() {
  const rows: { date: string; what: string; stamp: "sage" | "lavender" | "rose" }[] = [
    {
      date: "12 September",
      what: "Community buildings fund · Year 1 monitoring return",
      stamp: "lavender",
    },
    {
      date: "30 September",
      what: "County foundation · end-of-grant report",
      stamp: "sage",
    },
    {
      date: "14 July",
      what: "Youth trust · impact update",
      stamp: "rose",
    },
  ];
  const stampClass = {
    sage: "bg-pale-sage",
    lavender: "bg-lavender-mist",
    rose: "bg-dusty-rose",
  } as const;
  const stampLabel = {
    sage: "Upcoming",
    lavender: "Drafting",
    rose: "Sent",
  } as const;
  return (
    <Frame
      ariaLabel="Representative reporting calendar listing three funder returns across the year: one being drafted, one upcoming and one already sent"
      caption="Illustration of the tenant-wide reporting calendar: every return due across every grant in one list, each with its status — drafting, upcoming or sent."
    >
      <p className="mt-4 text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
        Reporting calendar · every grant, one list
      </p>
      <div className="mt-2 flex flex-col">
        {rows.map((row, i) => (
          <div
            key={row.what}
            className={`flex items-center justify-between gap-3 py-3.5 ${i > 0 ? "border-t border-bone" : ""}`}
          >
            <div>
              <p className="text-[12px] text-slate tabular-nums">{row.date}</p>
              <p className="mt-0.5 text-[14px] text-ink">{row.what}</p>
            </div>
            <span
              className={`inline-flex shrink-0 items-center rounded-full px-3 py-1 text-[12px] font-medium text-ink ${stampClass[row.stamp]}`}
            >
              {stampLabel[row.stamp]}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-3 border-t border-bone pt-3 text-[12px] leading-[1.5] text-slate">
        Each return assembles from the impact evidence already recorded
        against its grant.
      </p>
    </Frame>
  );
}
