import { ogCard, OG_SIZE } from "./og-card";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt =
  "Flowgrid OS — turn what your organisation knows into work you can trust";

export default function Image() {
  return ogCard({
    kicker: "AI operations workspace",
    title: "Turn what your organisation knows into work you can trust.",
  });
}
