/* Composed, clearly-labelled representative product view: a cited answer
 * beside its source, a confirmed claim and a project output cue. All data
 * is example data — no customer information. */

export function HeroVisual() {
  return (
    <figure aria-label="Representative product view showing a cited answer, its source document, a confirmed organisational fact and a report export">
      <div className="rounded-[24px] border border-stone bg-canvas p-5">
        <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-slate">
          Representative product view — example data
        </p>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {/* Cited answer */}
          <div className="rounded-lg border border-bone p-4">
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
              Ask the vault
            </p>
            <p className="mt-2 text-[14px] leading-[1.5] text-ink">
              &ldquo;What match funding did we commit to in the hall
              refurbishment bid?&rdquo;
            </p>
            <p className="mt-3 text-[14px] leading-[1.5] text-slate">
              The bid commits £18,500 of match funding from reserves, agreed
              by trustees on 14 May.{" "}
              <span className="inline-flex items-center rounded-full border border-deep-violet px-2 py-0.5 text-[12px] font-medium text-deep-violet">
                Source, p.4
              </span>
            </p>
          </div>

          {/* Source excerpt */}
          <div className="rounded-lg border border-bone bg-band p-4">
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
              Village-Hall-Bid.pdf · page 4
            </p>
            <p className="mt-2 text-[13px] leading-[1.55] text-slate">
              …the Trust will contribute{" "}
              <mark className="bg-lavender-mist/60 px-0.5 text-ink">
                £18,500 in match funding from unrestricted reserves
              </mark>
              , as resolved at the trustee meeting of 14 May…
            </p>
          </div>

          {/* Confirmed claim */}
          <div className="flex items-center justify-between gap-3 rounded-lg border border-bone p-4">
            <div>
              <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
                Claims register
              </p>
              <p className="mt-1 text-[14px] text-ink">
                Registered charity · no. 1198765
              </p>
            </div>
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-grounded-tint px-3 py-1 text-[12px] font-medium text-grounded">
              Confirmed
            </span>
          </div>

          {/* Output cue */}
          <div className="flex items-center justify-between gap-3 rounded-lg border border-bone p-4">
            <div>
              <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
                Project output
              </p>
              <p className="mt-1 text-[14px] text-ink">
                August monthly report
              </p>
            </div>
            <span className="inline-flex shrink-0 items-center rounded-full border border-burnt-amber px-3 py-1 text-[12px] font-medium text-burnt-amber">
              Export PDF
            </span>
          </div>
        </div>
      </div>
      <figcaption className="sr-only">
        Illustration of Flowgrid answering a question with a citation that
        links to the source page, alongside a confirmed claim and a one-click
        report export.
      </figcaption>
    </figure>
  );
}
