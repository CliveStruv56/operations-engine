import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteHeader } from "./site-header";
import { SiteFooter } from "./site-footer";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://flowgridos.co.uk";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Flowgrid OS — Turn what your organisation knows into work you can trust",
    template: "%s — Flowgrid OS",
  },
  description:
    "Flowgrid connects your source documents, confirmed facts and live projects in one workspace — cited answers, repeatable workflows and finished, branded outputs.",
  openGraph: {
    siteName: "Flowgrid OS",
    type: "website",
    locale: "en_GB",
  },
};

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-canvas focus:px-4 focus:py-2 focus:text-[14px]"
      >
        Skip to content
      </a>
      <SiteHeader />
      <main id="main" className="flex-1">
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
