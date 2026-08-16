import { ogCard, OG_SIZE } from "../og-card";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "About Flowgrid OS";

export default function Image() {
  return ogCard({
    kicker: "About",
    title: "Small organisations run on knowledge. Most of it is locked in old documents.",
  });
}
