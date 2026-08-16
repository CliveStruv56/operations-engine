import type { Metadata } from "next";
import { LegalPage } from "../legal";

export const metadata: Metadata = {
  title: "Cookies",
  description: "How the Flowgrid OS website uses cookies.",
  alternates: { canonical: "/cookies" },
  robots: { index: false },
};

export default function CookiesPage() {
  return (
    <LegalPage title="Cookies" updated="16 August 2026">
      <section>
        <h2>What this site sets</h2>
        <p>
          The public website currently sets no marketing or advertising
          cookies and runs no third-party trackers. Signing in to a Flowgrid
          workspace sets strictly necessary authentication cookies, which are
          required for the service to work and are not used for tracking.
        </p>
      </section>
      <section>
        <h2>Analytics</h2>
        <p>
          If we introduce analytics, it will be consent-aware and this page
          will be updated first, with a means to accept or decline
          non-essential cookies before any are set.
        </p>
      </section>
    </LegalPage>
  );
}
