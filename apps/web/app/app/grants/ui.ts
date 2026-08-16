// Grantwork styling, re-exported from the shared Hearth primitives.
//
// This file used to hold its own copies, on the reasoning that a change to one
// vertical's UI should not silently restyle another. In practice the copies
// drifted instead of protecting anything — Grantwork ended up on `bg-surface`
// and `border-line` while the claims register moved to `bg-card` and
// `border-edge`, which are the same colours under different names. Divergence
// where it is wanted should be a deliberate override at the call site, not five
// near-identical constants nobody can diff by eye.
export {
  btnPrimarySm as btn,
  btnQuiet as btnGhost,
  card,
  inputCompact as input,
  th,
} from "@/components/ui/styles";
