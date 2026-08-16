import { ogCard, OG_SIZE } from "../../og-card";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Groundwork — community-led development projects on Flowgrid OS";

export default function Image() {
  return ogCard({
    kicker: "Groundwork",
    title: "Keep the project record current. Let the client report follow.",
  });
}
