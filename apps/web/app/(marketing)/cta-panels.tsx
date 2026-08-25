import { Kicker } from "./ui";

/* Content panels that fill the CTA sections' right column — the review's
 * "dead column" finding. Both describe a real process, so the ordering
 * devices (minute ranges, step numbers) encode true sequence, not
 * decoration. */

const AGENDA: { time: string; what: string }[] = [
  { time: "0–5", what: "Your workflow, as you run it today" },
  { time: "5–15", what: "The same workflow set up in Flowgrid, on representative data" },
  { time: "15–20", what: "Fit, questions and pilot next steps" },
];

export function DemoAgendaPanel() {
  return (
    <div className="rounded-lg border border-bone bg-canvas p-6">
      <Kicker>The 20 minutes</Kicker>
      <ul className="mt-5 flex flex-col">
        {AGENDA.map((row, i) => (
          <li
            key={row.time}
            className={`flex items-baseline gap-4 py-3.5 ${i > 0 ? "border-t border-bone" : ""}`}
          >
            <span className="inline-flex shrink-0 items-center rounded-full border border-bone px-3 py-0.5 text-[13px] font-medium tabular-nums text-slate">
              {row.time}
            </span>
            <span className="text-[15px] leading-[1.45] text-ink">{row.what}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 border-t border-bone pt-4 text-[13px] leading-[1.5] text-slate">
        No slides, no signup — a screen share around work you already do.
      </p>
    </div>
  );
}

const PILOT_STEPS: string[] = [
  "Bring one live piece of work and the documents behind it",
  "We set it up together, in your own isolated workspace",
  "You produce one real deliverable from it — cited, reviewed, exported",
];

export function PilotShapePanel() {
  return (
    <div className="rounded-lg border border-bone bg-canvas p-6">
      <Kicker>What a pilot looks like</Kicker>
      <ol className="mt-5 flex flex-col">
        {PILOT_STEPS.map((step, i) => (
          <li
            key={step}
            className={`flex items-baseline gap-4 py-3.5 ${i > 0 ? "border-t border-bone" : ""}`}
          >
            <span className="inline-flex h-7 w-7 shrink-0 translate-y-1 items-center justify-center rounded-full border border-deep-violet text-[13px] font-medium tabular-nums text-deep-violet">
              {i + 1}
            </span>
            <span className="text-[15px] leading-[1.45] text-ink">{step}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
