import { ogCard, OG_SIZE } from "../og-card";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Book a 20-minute Flowgrid OS demo";

export default function Image() {
  return ogCard({
    kicker: "Contact",
    title: "Bring one repeated workflow. We'll show you how it fits.",
  });
}
