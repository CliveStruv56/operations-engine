import type { ReactNode } from "react";
import { Kicker } from "./ui";

/* Shared shell for legal pages. Copy is a working draft — final wording
 * must be approved before production form collection (PRD §11). */

export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-[760px] px-6 pb-24 pt-14 lg:pt-20">
      <Kicker>Legal</Kicker>
      <h1 className="mt-4 text-[40px] font-light leading-[1.15] tracking-[-0.92px] text-ink">
        {title}
      </h1>
      <p className="mt-3 text-[14px] text-slate">Last updated {updated}. Draft pending legal review.</p>
      <div className="mt-10 space-y-8 text-[16px] leading-[1.55] text-slate [&_h2]:text-[22px] [&_h2]:font-medium [&_h2]:tracking-[-0.22px] [&_h2]:text-ink [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1.5">
        {children}
      </div>
    </div>
  );
}
