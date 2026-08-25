import type { ReactNode } from "react";

/* Spot illustrations for the marketing concept cards. One fixed vocabulary
 * so they read as a family: 1.5px ink line work, var(--faint) for back
 * layers, pill corners echoing the CTA buttons, and the two washes carrying
 * the same meaning as the workflow diagram — amber for the thing Flowgrid
 * owns (records, exports), deep violet for trust surfaces (citations,
 * confirmed facts). Decorative by design: every spot sits beside copy that
 * says the same thing, so the SVG is aria-hidden (PRD §8 accessibility). */

const INK = "var(--ink)";
const FAINT = "var(--faint)";
const SOFT = "var(--subtle)";
const AMBER = "var(--burnt-amber)";
const VIOLET = "var(--deep-violet)";
const VIOLET_WASH = "var(--accent-tint)";
const AMBER_WASH = "#f2e9dc"; // marketing-only, matches workflow-diagram.tsx
const PAPER = "var(--canvas)";

export type SpotName =
  | "evidence"
  | "structure"
  | "output"
  | "citation"
  | "claim"
  | "plan"
  | "export"
  | "gates"
  | "registers"
  | "calendar"
  | "impact";

const SPOTS: Record<SpotName, ReactNode> = {
  /* A stack of documents; the cited line leaves the page as a source chip. */
  evidence: (
    <>
      <rect x="34" y="30" width="80" height="70" rx="6" fill={PAPER} stroke={FAINT} />
      <rect x="42" y="22" width="80" height="70" rx="6" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="54" y1="42" x2="110" y2="42" stroke={FAINT} strokeWidth="1.5" />
      <line x1="54" y1="54" x2="110" y2="54" stroke={FAINT} strokeWidth="1.5" />
      <line x1="54" y1="66" x2="92" y2="66" stroke={VIOLET} strokeWidth="3" />
      <path d="M 96 66 L 116 66" fill="none" stroke={VIOLET} strokeWidth="1.5" />
      <rect x="120" y="55" width="52" height="22" rx="11" fill={VIOLET_WASH} stroke={VIOLET} strokeWidth="1.5" />
      <text x="146" y="70" textAnchor="middle" fontSize="10.5" fill={VIOLET}>
        p.4
      </text>
    </>
  ),

  /* A portfolio grid with one engagement visibly mid-flight. */
  structure: (
    <>
      <rect x="36" y="22" width="38" height="30" rx="5" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <rect x="82" y="22" width="38" height="30" rx="5" fill={PAPER} stroke={FAINT} strokeWidth="1.5" />
      <rect x="128" y="22" width="38" height="30" rx="5" fill={PAPER} stroke={FAINT} strokeWidth="1.5" />
      <rect x="36" y="60" width="38" height="30" rx="5" fill={PAPER} stroke={FAINT} strokeWidth="1.5" />
      <rect x="82" y="60" width="38" height="30" rx="5" fill={AMBER_WASH} stroke={AMBER} strokeWidth="1.5" />
      <circle cx="94" cy="75" r="3" fill={AMBER} />
      <line x1="103" y1="75" x2="112" y2="75" stroke={AMBER} strokeWidth="2" />
      <rect x="128" y="60" width="38" height="30" rx="5" fill={PAPER} stroke={FAINT} strokeWidth="1.5" />
    </>
  ),

  /* A finished document leaving the workspace as a branded export. */
  output: (
    <>
      <rect x="46" y="20" width="72" height="84" rx="6" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="58" y1="38" x2="106" y2="38" stroke={INK} strokeWidth="2.5" />
      <line x1="58" y1="52" x2="106" y2="52" stroke={FAINT} strokeWidth="1.5" />
      <line x1="58" y1="62" x2="106" y2="62" stroke={FAINT} strokeWidth="1.5" />
      <line x1="58" y1="72" x2="94" y2="72" stroke={FAINT} strokeWidth="1.5" />
      <path d="M 122 62 L 144 62" fill="none" stroke={AMBER} strokeWidth="1.5" />
      <path d="M 139 56 L 146 62 L 139 68" fill="none" stroke={AMBER} strokeWidth="1.5" />
      <rect x="150" y="50" width="36" height="24" rx="12" fill={AMBER_WASH} stroke={AMBER} strokeWidth="1.5" />
      <text x="168" y="66" textAnchor="middle" fontSize="10.5" fill={AMBER}>
        PDF
      </text>
    </>
  ),

  /* An answer carrying a citation marker that opens the source page. */
  citation: (
    <>
      <rect x="30" y="26" width="86" height="40" rx="10" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="42" y1="40" x2="104" y2="40" stroke={FAINT} strokeWidth="1.5" />
      <line x1="42" y1="52" x2="88" y2="52" stroke={FAINT} strokeWidth="1.5" />
      <line x1="30" y1="88" x2="96" y2="88" stroke={INK} strokeWidth="1.5" />
      <rect x="100" y="79" width="20" height="18" rx="6" fill={VIOLET_WASH} stroke={VIOLET} strokeWidth="1.5" />
      <text x="110" y="92" textAnchor="middle" fontSize="10" fill={VIOLET}>
        1
      </text>
      <path d="M 124 88 L 140 88" fill="none" stroke={VIOLET} strokeWidth="1.5" />
      <path d="M 136 83 L 142 88 L 136 93" fill="none" stroke={VIOLET} strokeWidth="1.5" />
      <rect x="146" y="58" width="38" height="52" rx="5" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="152" y1="70" x2="178" y2="70" stroke={FAINT} strokeWidth="1.5" />
      <rect x="152" y="78" width="26" height="9" rx="2" fill={VIOLET_WASH} stroke={VIOLET} />
      <line x1="152" y1="98" x2="178" y2="98" stroke={FAINT} strokeWidth="1.5" />
    </>
  ),

  /* One confirmed fact fanning out into two documents. */
  claim: (
    <>
      <rect x="28" y="48" width="84" height="26" rx="13" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="40" y1="61" x2="82" y2="61" stroke={FAINT} strokeWidth="2" />
      <circle cx="99" cy="61" r="8" fill={VIOLET_WASH} stroke={VIOLET} strokeWidth="1.5" />
      <path d="M 95 61 L 98 64 L 104 57" fill="none" stroke={VIOLET} strokeWidth="1.5" />
      <path d="M 116 54 C 126 46, 128 43, 134 41" fill="none" stroke={VIOLET} strokeWidth="1.5" />
      <path d="M 130 38 L 137 40 L 133 46" fill="none" stroke={VIOLET} strokeWidth="1.5" />
      <path d="M 116 68 C 126 76, 128 79, 134 81" fill="none" stroke={VIOLET} strokeWidth="1.5" />
      <path d="M 133 76 L 137 82 L 130 84" fill="none" stroke={VIOLET} strokeWidth="1.5" />
      <rect x="140" y="22" width="44" height="34" rx="5" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="148" y1="34" x2="176" y2="34" stroke={FAINT} strokeWidth="1.5" />
      <line x1="148" y1="44" x2="168" y2="44" stroke={FAINT} strokeWidth="1.5" />
      <rect x="140" y="66" width="44" height="34" rx="5" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="148" y1="78" x2="176" y2="78" stroke={FAINT} strokeWidth="1.5" />
      <line x1="148" y1="88" x2="168" y2="88" stroke={FAINT} strokeWidth="1.5" />
    </>
  ),

  /* A checklist with owned tasks; two done, one waiting. */
  plan: (
    <>
      <rect x="36" y="20" width="128" height="84" rx="8" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <rect x="48" y="31" width="14" height="14" rx="4" fill={AMBER} />
      <path d="M 51 38 L 54 41 L 59 34" fill="none" stroke={PAPER} strokeWidth="1.5" />
      <line x1="70" y1="38" x2="126" y2="38" stroke={FAINT} strokeWidth="1.5" />
      <circle cx="142" cy="38" r="7" fill={PAPER} stroke={INK} strokeWidth="1.25" />
      <rect x="48" y="53" width="14" height="14" rx="4" fill={AMBER} />
      <path d="M 51 60 L 54 63 L 59 56" fill="none" stroke={PAPER} strokeWidth="1.5" />
      <line x1="70" y1="60" x2="126" y2="60" stroke={FAINT} strokeWidth="1.5" />
      <circle cx="142" cy="60" r="7" fill={PAPER} stroke={INK} strokeWidth="1.25" />
      <rect x="48" y="75" width="14" height="14" rx="4" fill={PAPER} stroke={FAINT} strokeWidth="1.5" />
      <line x1="70" y1="82" x2="126" y2="82" stroke={FAINT} strokeWidth="1.5" />
      <circle cx="142" cy="82" r="7" fill={PAPER} stroke={FAINT} strokeWidth="1.25" />
    </>
  ),

  /* One conversation becoming slides and a PDF, both branded. */
  export: (
    <>
      <rect x="30" y="24" width="60" height="72" rx="6" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="40" y1="40" x2="80" y2="40" stroke={INK} strokeWidth="2.5" />
      <line x1="40" y1="52" x2="80" y2="52" stroke={FAINT} strokeWidth="1.5" />
      <line x1="40" y1="62" x2="80" y2="62" stroke={FAINT} strokeWidth="1.5" />
      <line x1="40" y1="72" x2="68" y2="72" stroke={FAINT} strokeWidth="1.5" />
      <path d="M 96 50 L 110 45" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <path d="M 105 42 L 112 44 L 108 50" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <path d="M 96 74 L 110 80" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <path d="M 108 75 L 112 81 L 105 83" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <rect x="118" y="26" width="56" height="38" rx="5" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="126" y1="38" x2="150" y2="38" stroke={AMBER} strokeWidth="2.5" />
      <line x1="126" y1="47" x2="166" y2="47" stroke={FAINT} strokeWidth="1.5" />
      <line x1="126" y1="55" x2="154" y2="55" stroke={FAINT} strokeWidth="1.5" />
      <rect x="118" y="74" width="44" height="22" rx="11" fill={AMBER_WASH} stroke={AMBER} strokeWidth="1.5" />
      <text x="140" y="89" textAnchor="middle" fontSize="10.5" fill={AMBER}>
        PDF
      </text>
    </>
  ),

  /* The stage-gate spine, with what's needed to progress at the live gate. */
  gates: (
    <>
      <line x1="36" y1="50" x2="164" y2="50" stroke={AMBER} />
      <circle cx="36" cy="50" r="8" fill={AMBER} />
      <circle cx="68" cy="50" r="8" fill={AMBER} />
      <circle cx="100" cy="50" r="8" fill={AMBER} />
      <circle cx="132" cy="50" r="8" fill={PAPER} stroke={AMBER} strokeWidth="1.5" />
      <circle cx="164" cy="50" r="8" fill={PAPER} stroke={AMBER} strokeWidth="1.5" />
      <line x1="100" y1="60" x2="100" y2="70" stroke={FAINT} strokeWidth="1.5" />
      <rect x="76" y="72" width="48" height="20" rx="10" fill={AMBER_WASH} stroke={AMBER} strokeWidth="1.5" />
      <line x1="86" y1="82" x2="114" y2="82" stroke={AMBER} strokeWidth="1.5" />
    </>
  ),

  /* Three registers recorded once, converging into one draft. */
  registers: (
    <>
      <rect x="28" y="24" width="64" height="22" rx="11" fill={PAPER} stroke={AMBER} strokeWidth="1.5" />
      <line x1="38" y1="35" x2="70" y2="35" stroke={FAINT} strokeWidth="1.5" />
      <rect x="28" y="52" width="64" height="22" rx="11" fill={PAPER} stroke={AMBER} strokeWidth="1.5" />
      <line x1="38" y1="63" x2="70" y2="63" stroke={FAINT} strokeWidth="1.5" />
      <rect x="28" y="80" width="64" height="22" rx="11" fill={PAPER} stroke={AMBER} strokeWidth="1.5" />
      <line x1="38" y1="91" x2="70" y2="91" stroke={FAINT} strokeWidth="1.5" />
      <path d="M 96 35 C 114 35, 118 44, 130 50" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <path d="M 126 45 L 132 51 L 124 52" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <path d="M 96 63 L 130 63" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <path d="M 127 59 L 132 63 L 127 67" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <path d="M 96 91 C 114 91, 118 82, 130 76" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <path d="M 124 74 L 132 75 L 126 81" fill="none" stroke={SOFT} strokeWidth="1.2" />
      <rect x="136" y="34" width="48" height="60" rx="6" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="144" y1="48" x2="176" y2="48" stroke={FAINT} strokeWidth="1.5" />
      <line x1="144" y1="58" x2="176" y2="58" stroke={FAINT} strokeWidth="1.5" />
      <line x1="144" y1="68" x2="176" y2="68" stroke={FAINT} strokeWidth="1.5" />
      <line x1="144" y1="78" x2="164" y2="78" stroke={FAINT} strokeWidth="1.5" />
    </>
  ),

  /* A deadline recorded on the calendar the day the award lands. */
  calendar: (
    <>
      <rect x="36" y="22" width="76" height="64" rx="6" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <rect x="37" y="23" width="74" height="14" rx="4" fill={AMBER_WASH} />
      <line x1="36" y1="37" x2="112" y2="37" stroke={INK} strokeWidth="1" />
      <circle cx="50" cy="48" r="1.5" fill={FAINT} />
      <circle cx="66" cy="48" r="1.5" fill={FAINT} />
      <circle cx="82" cy="48" r="1.5" fill={FAINT} />
      <circle cx="98" cy="48" r="1.5" fill={FAINT} />
      <circle cx="50" cy="62" r="1.5" fill={FAINT} />
      <circle cx="66" cy="62" r="1.5" fill={FAINT} />
      <circle cx="82" cy="62" r="1.5" fill={FAINT} />
      <circle cx="98" cy="62" r="1.5" fill={FAINT} />
      <circle cx="50" cy="76" r="1.5" fill={FAINT} />
      <circle cx="66" cy="76" r="1.5" fill={FAINT} />
      <circle cx="82" cy="62" r="7" fill="none" stroke={AMBER} strokeWidth="1.5" />
      <rect x="124" y="46" width="56" height="22" rx="11" fill={PAPER} stroke={INK} strokeWidth="1.5" />
      <line x1="134" y1="57" x2="158" y2="57" stroke={FAINT} strokeWidth="1.5" />
      <circle cx="169" cy="57" r="6" fill={VIOLET_WASH} stroke={VIOLET} strokeWidth="1.5" />
      <path d="M 166 57 L 168 59 L 172 54" fill="none" stroke={VIOLET} strokeWidth="1.25" />
    </>
  ),

  /* Impact evidence accumulating through the year, every figure recorded. */
  impact: (
    <>
      <line x1="36" y1="96" x2="164" y2="96" stroke={FAINT} strokeWidth="1.5" />
      <rect x="52" y="68" width="20" height="28" rx="4" fill={AMBER_WASH} stroke={AMBER} strokeWidth="1.5" />
      <rect x="90" y="52" width="20" height="44" rx="4" fill={AMBER_WASH} stroke={AMBER} strokeWidth="1.5" />
      <rect x="128" y="32" width="20" height="64" rx="4" fill={AMBER_WASH} stroke={AMBER} strokeWidth="1.5" />
      <circle cx="62" cy="62" r="3" fill={VIOLET} />
      <circle cx="100" cy="46" r="3" fill={VIOLET} />
      <circle cx="138" cy="26" r="3" fill={VIOLET} />
    </>
  ),
};

export function Spot({
  name,
  className = "",
}: {
  name: SpotName;
  className?: string;
}) {
  return (
    <svg viewBox="0 0 200 120" aria-hidden className={className}>
      {SPOTS[name]}
    </svg>
  );
}
