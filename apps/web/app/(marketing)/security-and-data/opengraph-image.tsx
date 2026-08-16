import { ogCard, OG_SIZE } from "../og-card";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Flowgrid OS security and data handling, in plain English";

export default function Image() {
  return ogCard({
    kicker: "Security & data",
    title: "The questions you should ask any AI vendor — answered plainly.",
  });
}
