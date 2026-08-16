import type { Metadata } from "next";
import { Kicker } from "../ui";
import { DemoForm } from "./demo-form";

export const metadata: Metadata = {
  title: "Book a demo",
  description:
    "Book a 20-minute Flowgrid demo around a report, bid or return you already produce — or ask us a question directly.",
  alternates: { canonical: "/contact" },
};

export default function ContactPage() {
  return (
    <div className="mx-auto grid w-full max-w-[1200px] gap-12 px-6 pb-24 pt-14 lg:grid-cols-[5fr_7fr] lg:pt-20">
      <div>
        <Kicker>Contact</Kicker>
        <h1 className="mt-4 text-[40px] font-light leading-[1.15] tracking-[-0.92px] text-ink md:text-[56px]">
          Book a 20-minute demo.
        </h1>
        <p className="mt-6 text-[18px] leading-[1.42] tracking-[-0.14px] text-slate">
          Bring one repeated workflow — a monthly report, a funding bid, a
          monitoring return — and we&rsquo;ll show you how it fits. No slide
          deck, just the product on something real.
        </p>
        <div className="mt-10 rounded-lg border border-bone p-5">
          <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
            Prefer email?
          </p>
          <p className="mt-2 text-[16px] text-ink">
            <a
              href="mailto:hello@flowgridos.co.uk"
              className="text-deep-violet underline-offset-4 hover:underline"
            >
              hello@flowgridos.co.uk
            </a>
          </p>
          <p className="mt-2 text-[14px] leading-[1.5] text-slate">
            We aim to reply within two working days.
          </p>
        </div>
      </div>
      <div className="rounded-[24px] border border-stone p-6 md:p-10">
        <DemoForm />
      </div>
    </div>
  );
}
