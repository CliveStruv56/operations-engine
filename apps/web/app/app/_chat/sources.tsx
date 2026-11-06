import { DocIcon, GlobeIcon } from "@/components/icons";
import type { Citation } from "./types";

function domainOf(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

/** Cite renderer for AnswerMarkdown: [n] markers that match a real citation
 * become buttons; anything else stays literal text. */
export function citeButton(
  citations: Citation[],
  onCite: (n: number) => void
): (n: number) => React.ReactNode {
  const nums = new Set(citations.map((c) => c.n));
  // Returns nodes, not a component — the display-name rule misfires here.
  // eslint-disable-next-line react/display-name
  return (n) =>
    nums.has(n) ? (
      <button
        onClick={() => onCite(n)}
        className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-[5px] bg-accent-tint px-1 align-[2px] text-xs font-extrabold text-electric-blue hover:bg-deep-violet hover:text-white"
        aria-label={`Source ${n}`}
      >
        {n}
      </button>
    ) : (
      `[${n}]`
    );
}

export function SourceCard({ c }: { c: Citation }) {
  const web = c.source_type === "web";
  return (
    <div id={`src-${c.chunk_id}`} className="rounded-[11px] border border-edge bg-canvas p-3">
      <div className="flex items-center gap-2 text-xs font-bold">
        <span className="mr-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-[5px] bg-accent-tint px-1 text-xs font-extrabold text-electric-blue">
          {c.n}
        </span>
        {web ? (
          <GlobeIcon className="h-3 w-3 text-electric-blue" />
        ) : (
          <DocIcon className="h-3 w-3 text-electric-blue" />
        )}
        <span className="min-w-0 truncate">{c.title}</span>
        <em className="ml-auto shrink-0 text-xs font-semibold not-italic text-faint">
          {web
            ? domainOf(c.url)
            : c.page_start != null
              ? `p. ${c.page_start}${
                  c.page_end != null && c.page_end !== c.page_start ? `–${c.page_end}` : ""
                }`
              : ""}
        </em>
      </div>
      <p className="mt-1.5 line-clamp-4 text-xs leading-relaxed text-subtle italic">
        &ldquo;{c.snippet}&rdquo;
      </p>
      {web && c.url && (
        <a
          href={c.url}
          target="_blank"
          rel="noreferrer"
          className="mt-1.5 block truncate text-xs font-bold text-electric-blue hover:underline"
        >
          Open source ↗
        </a>
      )}
    </div>
  );
}
