// The canonical Hearth control classes.
//
// Before this file, fourteen screens each kept their own `const btn = "..."`
// and they had drifted: some said `bg-card`, some the legacy `bg-surface`;
// some `border-edge`, some `border-line`. Radius was written as `rounded-[10px]`
// even though `--radius-btn` is 10px. Everything here is expressed in tokens so
// a change to Hearth lands once.
//
// Prefer the components in this folder for new work — they carry the states and
// the ARIA. These strings exist for the places that style a bare element, and
// so the older screens can share one definition without being rewritten.

/** Focus is the global `:focus-visible` outline from globals.css; controls do
 *  not add their own ring, or focused buttons get two. */
const pressable = "active:scale-[.99] disabled:cursor-not-allowed";

/** Filled terracotta. Hearth allows three of these per view, so a screen with
 *  two primary buttons is a screen with a hierarchy problem. */
export const btnPrimary =
  `inline-flex min-h-9 items-center justify-center gap-2 rounded-btn bg-accent px-4 py-2 ` +
  `text-sm font-semibold text-accent-ink transition-colors hover:bg-accent-deep ` +
  // The kit specifies `text-faint` when disabled, which is 4.42:1 on --edge and
  // misses AA for 13.5px text. --subtle is the same idea at 5.64:1.
  `disabled:bg-edge disabled:text-subtle ${pressable}`;

/** Row-height primary, for table rows and tab toolbars where a 36px control
 *  would break the line. Still clears the 24px minimum target. */
export const btnPrimarySm =
  `inline-flex min-h-7 items-center justify-center gap-1.5 rounded-btn bg-accent px-3 py-1.5 ` +
  `text-sm font-semibold text-accent-ink transition-colors hover:bg-accent-deep ` +
  `disabled:bg-edge disabled:text-subtle ${pressable}`;

/** Outlined. The eye should land on the primary button before this one. */
export const btnSecondary =
  `inline-flex min-h-9 items-center justify-center gap-2 rounded-btn border border-edge-strong ` +
  `bg-card px-4 py-2 text-sm font-semibold text-subtle transition-colors hover:border-electric-blue ` +
  `hover:text-electric-blue disabled:bg-edge disabled:text-subtle ${pressable}`;

/** Destructive. Always pair with a verb — "Delete project", never a red icon. */
export const btnDanger =
  `inline-flex min-h-9 items-center justify-center gap-2 rounded-btn bg-danger px-4 py-2 ` +
  `text-sm font-semibold text-accent-ink transition-colors hover:bg-danger-deep ` +
  `disabled:bg-edge disabled:text-subtle ${pressable}`;

/** The quiet text button. `min-h-6` gives it a 24px hit target (WCAG 2.5.8)
 *  without making it look heavier than it should. */
export const btnQuiet =
  `inline-flex min-h-6 items-center gap-1 text-xs font-semibold text-subtle underline ` +
  `decoration-edge-strong underline-offset-2 transition-colors hover:text-ink ` +
  `hover:decoration-electric-blue disabled:cursor-not-allowed disabled:text-faint disabled:no-underline`;

/** 36×36 icon button. Requires an aria-label at the call site. */
export const btnIcon =
  `inline-flex h-9 w-9 items-center justify-center rounded-btn border border-edge bg-card ` +
  `text-subtle transition-colors hover:bg-sidebar hover:text-ink ${pressable}`;

export const input =
  `w-full rounded-btn border border-edge-input bg-card px-3 py-2 text-sm text-ink ` +
  `placeholder:text-faint focus:border-electric-blue focus:outline-none disabled:bg-sidebar ` +
  `disabled:text-subtle aria-[invalid=true]:border-danger`;

/** Same control, sized by its container instead of filling it — table cells and
 *  inline rows, where `w-full` stretches a select across the column. */
export const inputInline =
  `rounded-btn border border-edge-input bg-card px-3 py-2 text-sm text-ink ` +
  `placeholder:text-faint focus:border-electric-blue focus:outline-none disabled:bg-sidebar ` +
  `disabled:text-subtle aria-[invalid=true]:border-danger`;

/** Table cells and inline edits, where a full-height input would break the row. */
export const inputCompact =
  `rounded-btn border border-edge-input bg-card px-2 py-1 text-sm text-ink ` +
  `placeholder:text-faint focus:border-electric-blue focus:outline-none disabled:bg-sidebar ` +
  `disabled:text-subtle aria-[invalid=true]:border-danger`;

export const card = "rounded-card border border-edge bg-card shadow-card";
export const cardPadded = `${card} p-5`;

/** Uppercase micro-label, above a field or heading a section. */
export const label = "data mb-1 block text-subtle uppercase";

/** Table header cell. Pair with scope="col". */
export const th = "data px-4 py-2.5 text-left text-subtle uppercase";
