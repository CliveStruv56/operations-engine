/* End-to-end workflow diagram (PRD §6: "a single end-to-end workflow
 * diagram"). Static SVG in a server component — no JS shipped. Geometry is
 * fixed; content is a typed config per page so capability claims stay
 * reviewable, like SolutionContent. Colour rules: amber holds the record
 * (the thing Flowgrid owns), deep violet marks trust surfaces (confirmed
 * facts, citations), ink for what the customer already has. The amber wash
 * is marketing-only and deliberately not a globals.css token — the app's
 * pastel stamps remain a status taxonomy and must not gain a decorative
 * sibling there. */

export interface WorkflowDiagramContent {
  /** Full-sentence description of the mechanism for screen readers. */
  ariaLabel: string;
  vault: { caption: string; arrowLabel: string };
  facts: { caption: string; arrowLabel: string };
  record: {
    title: string;
    gatesDone: number;
    gatesTotal: number;
    spineLabel: string;
    chips: string[];
    footnote: string;
  };
  /** 3–4 entries; `violet` marks the trust-surface deliverable. */
  outputs: { label: string; violet?: boolean }[];
  outLabel: string;
  returnLabel: string;
}

const AMBER_WASH = "#f2e9dc";
const INK = "var(--ink)";
const SOFT = "var(--subtle)";
const FAINT = "var(--faint)";
const AMBER = "var(--burnt-amber)";
const VIOLET = "var(--deep-violet)";
const VIOLET_WASH = "var(--accent-tint)";

const W = 860;
const H = 340;
const RECORD = { x: 300, y: 62, w: 260, h: 196 };
const OUT_X = 660;
const OUT_W = 170;
const OUT_H = 44;
const OUT_GAP = 16;

function outputYs(count: number): number[] {
  const total = count * OUT_H + (count - 1) * (OUT_GAP);
  const top = 160 - total / 2;
  return Array.from({ length: count }, (_, i) => top + i * (OUT_H + OUT_GAP));
}

function chipWidth(label: string): number {
  return Math.round(label.length * 6.6) + 26;
}

export function WorkflowDiagram({ content }: { content: WorkflowDiagramContent }) {
  const { record, outputs } = content;
  const ys = outputYs(outputs.length);

  const gateXs = Array.from(
    { length: record.gatesTotal },
    (_, i) => 336 + (i * 188) / Math.max(record.gatesTotal - 1, 1),
  );

  const chipWidths = record.chips.map(chipWidth);
  const chipsTotal =
    chipWidths.reduce((a, b) => a + b, 0) + (record.chips.length - 1) * 8;
  const chipXs = chipWidths.map(
    (_, i) =>
      430 -
      chipsTotal / 2 +
      chipWidths.slice(0, i).reduce((a, b) => a + b + 8, 0),
  );

  // Out-arrows fan from the record's right edge to each output's left edge.
  const startYs = outputs.map((_, i) =>
    outputs.length === 1 ? 155 : 110 + (i * 90) / (outputs.length - 1),
  );

  return (
    <div className="overflow-x-auto">
      {/* PRD §9: motion is functional and optional. The citation loop — the
          one mark carrying the trust claim — draws in as the diagram scrolls
          into view. Pure CSS scroll-driven animation: no JS, static in
          browsers without animation-timeline, static under reduced motion. */}
      <style>{`
        @keyframes wfd-draw {
          from { clip-path: inset(-12% -3% -12% 101%); }
          to { clip-path: inset(-12% -3% -12% -3%); }
        }
        @keyframes wfd-fade {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @media (prefers-reduced-motion: no-preference) {
          @supports (animation-timeline: view()) {
            svg.wfd { view-timeline-name: --wfd; }
            .wfd-draw {
              animation: wfd-draw 1s ease-out both;
              animation-timeline: --wfd;
              animation-range: entry 30% contain 45%;
            }
            .wfd-fade {
              animation: wfd-fade 1s ease-out both;
              animation-timeline: --wfd;
              animation-range: entry 60% contain 60%;
            }
          }
        }
      `}</style>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={content.ariaLabel}
        className="wfd h-auto w-full min-w-[760px]"
      >
        <defs>
          <marker
            id="wfd-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L10,5 L0,10 z" fill={SOFT} />
          </marker>
          <marker
            id="wfd-arrow-violet"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L10,5 L0,10 z" fill={VIOLET} />
          </marker>
        </defs>

        {/* The vault: a stack of documents */}
        <rect x="30" y="88" width="150" height="46" rx="6" fill="var(--canvas)" stroke={FAINT} />
        <rect x="38" y="80" width="150" height="46" rx="6" fill="var(--canvas)" stroke={FAINT} />
        <rect x="46" y="72" width="150" height="46" rx="6" fill="var(--canvas)" stroke={INK} />
        <text x="121" y="99" textAnchor="middle" fontSize="12.5" fill={INK}>
          The vault
        </text>
        <text x="121" y="152" textAnchor="middle" fontSize="11" fill={SOFT}>
          {content.vault.caption}
        </text>

        {/* Confirmed facts: a trust surface */}
        <rect x="46" y="188" width="150" height="46" rx="6" fill={VIOLET_WASH} stroke={VIOLET} />
        <text x="121" y="207" textAnchor="middle" fontSize="12.5" fill={VIOLET}>
          Confirmed facts
        </text>
        <text x="121" y="223" textAnchor="middle" fontSize="10.5" fill={VIOLET}>
          {content.facts.caption}
        </text>

        {/* The live record */}
        <rect
          x={RECORD.x}
          y={RECORD.y}
          width={RECORD.w}
          height={RECORD.h}
          rx="8"
          fill={AMBER_WASH}
          stroke={AMBER}
        />
        <text x="430" y="92" textAnchor="middle" fontSize="14" fontWeight="600" fill={INK}>
          {record.title}
        </text>
        <line x1={gateXs[0]} y1="128" x2={gateXs[gateXs.length - 1]} y2="128" stroke={AMBER} />
        {gateXs.map((x, i) => (
          <circle
            key={x}
            cx={x}
            cy="128"
            r="7"
            fill={i < record.gatesDone ? AMBER : "var(--canvas)"}
            stroke={AMBER}
          />
        ))}
        <text x="430" y="153" textAnchor="middle" fontSize="11" fill={SOFT}>
          {record.spineLabel}
        </text>
        {record.chips.map((chip, i) => (
          <g key={chip}>
            <rect
              x={chipXs[i]}
              y="172"
              width={chipWidths[i]}
              height="26"
              rx="13"
              fill="var(--canvas)"
              stroke={AMBER}
            />
            <text
              x={chipXs[i] + chipWidths[i] / 2}
              y="189"
              textAnchor="middle"
              fontSize="11"
              fill={INK}
            >
              {chip}
            </text>
          </g>
        ))}
        <text x="430" y="236" textAnchor="middle" fontSize="11" fill={SOFT}>
          {record.footnote}
        </text>

        {/* Deliverables */}
        {outputs.map((out, i) => (
          <g key={out.label}>
            <rect
              x={OUT_X}
              y={ys[i]}
              width={OUT_W}
              height={OUT_H}
              rx="6"
              fill={out.violet ? VIOLET_WASH : "var(--canvas)"}
              stroke={out.violet ? VIOLET : INK}
            />
            <text
              x={OUT_X + OUT_W / 2}
              y={ys[i] + 27}
              textAnchor="middle"
              fontSize="12.5"
              fill={out.violet ? VIOLET : INK}
            >
              {out.label}
            </text>
          </g>
        ))}

        {/* Evidence in */}
        <path
          d="M 200 95 C 250 95, 250 120, 296 130"
          fill="none"
          stroke={SOFT}
          strokeWidth="1.2"
          markerEnd="url(#wfd-arrow)"
        />
        <text x="238" y="84" fontSize="11" fill={SOFT}>
          {content.vault.arrowLabel}
        </text>
        <path
          d="M 200 211 C 250 211, 250 195, 296 185"
          fill="none"
          stroke={SOFT}
          strokeWidth="1.2"
          markerEnd="url(#wfd-arrow)"
        />
        <text x="212" y="238" fontSize="11" fill={SOFT}>
          {content.facts.arrowLabel}
        </text>

        {/* Deliverables out */}
        {outputs.map((out, i) => (
          <path
            key={out.label}
            d={`M 560 ${startYs[i]} C 610 ${(startYs[i] + ys[i] + OUT_H / 2) / 2}, 612 ${
              ys[i] + OUT_H / 2
            }, 656 ${ys[i] + OUT_H / 2}`}
            fill="none"
            stroke={SOFT}
            strokeWidth="1.2"
            markerEnd="url(#wfd-arrow)"
          />
        ))}
        <text x="566" y="40" fontSize="11" fill={SOFT}>
          {content.outLabel}
        </text>

        {/* Citations resolve back to source — the trust loop */}
        <path
          className="wfd-draw"
          d={`M 745 ${ys[ys.length - 1] + OUT_H + 12} C 500 330, 220 306, 121 240`}
          fill="none"
          stroke={VIOLET}
          strokeWidth="1.2"
          strokeDasharray="4 4"
          markerEnd="url(#wfd-arrow-violet)"
        />
        <text
          className="wfd-fade"
          x="430"
          y="328"
          textAnchor="middle"
          fontSize="11"
          fill={VIOLET}
        >
          {content.returnLabel}
        </text>
      </svg>
    </div>
  );
}
