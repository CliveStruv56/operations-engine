import type { Metadata } from "next";
import Link from "next/link";
import { HeroVisual } from "./hero-visual";
import { HERO, HOME_META } from "./home-content";
import {
  AudiencesSection,
  BuiltNextSection,
  ClosingSection,
  InChargeBand,
  TrustBand,
  WorksTodayBand,
} from "./home-sections";
import { ctaGhost, DemoCta, Kicker } from "./ui";

export const metadata: Metadata = {
  // Absolute: the marketing layout's "%s — Flowgrid OS" template would
  // repeat the product name.
  title: { absolute: HOME_META.title },
  description: HOME_META.description,
  alternates: { canonical: "/" },
};

/* Home page (consultancy-first rewrite, Nov 2026). Copy: home-content.ts.
 * Order: hero, who it's for, what works today, being built next, you stay
 * in charge, your data, next step. */
export default function HomePage() {
  return (
    <>
      <section className="mx-auto grid w-full max-w-[1200px] gap-12 px-6 pb-16 pt-14 lg:grid-cols-[7fr_6fr] lg:items-center lg:pt-20">
        <div>
          <Kicker>{HERO.kicker}</Kicker>
          <h1 className="mt-4 text-[40px] font-light leading-[1.1] tracking-[-0.92px] text-ink md:text-[60px] md:tracking-[-1.3px]">
            {HERO.headline}
          </h1>
          <p className="mt-6 max-w-xl text-[18px] leading-[1.42] tracking-[-0.14px] text-slate">
            {HERO.subline}
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            <DemoCta label={HERO.primaryCta} />
            <Link href={HERO.secondaryCta.href} className={ctaGhost}>
              {HERO.secondaryCta.label}
            </Link>
          </div>
          <p className="mt-6 max-w-xl text-[14px] leading-[1.5] text-slate">{HERO.smallPrint}</p>
        </div>
        <HeroVisual />
      </section>

      <AudiencesSection />
      <WorksTodayBand />
      <BuiltNextSection />
      <InChargeBand />
      <TrustBand />
      <ClosingSection />
    </>
  );
}
