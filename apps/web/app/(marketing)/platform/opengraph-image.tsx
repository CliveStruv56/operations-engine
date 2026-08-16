import { ogCard, OG_SIZE } from "../og-card";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Flowgrid OS platform — vault, claims, projects and outputs";

export default function Image() {
  return ogCard({
    kicker: "Platform",
    title: "A workspace built on evidence, not vibes.",
  });
}
