import { ogCard, OG_SIZE } from "../../og-card";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Grantwork — grant applications and reporting on Flowgrid OS";

export default function Image() {
  return ogCard({
    kicker: "Grantwork",
    title: "Carry evidence from application to monitoring return.",
  });
}
