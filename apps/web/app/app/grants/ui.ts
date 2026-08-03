// Shared styling primitives for the Grantwork pages, mirroring the project
// room's. Module-local rather than imported across modules, so a change to one
// vertical's UI cannot silently restyle another.
export const input = "rounded-[10px] border border-line bg-surface px-2 py-1 text-sm";
export const btn =
  "rounded-[10px] bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50";
export const btnGhost = "text-xs text-ink-muted underline hover:text-ink";
export const card = "rounded-card border border-edge bg-surface";
export const th = "data px-4 py-2.5 text-left text-ink-muted uppercase";
