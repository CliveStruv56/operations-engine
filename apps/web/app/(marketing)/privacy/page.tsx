import type { Metadata } from "next";
import { LegalPage } from "../legal";

export const metadata: Metadata = {
  title: "Privacy notice",
  description: "How Flowgrid OS handles personal data on this website.",
  alternates: { canonical: "/privacy" },
  robots: { index: false },
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy notice" updated="16 August 2026">
      <section>
        <h2>Who we are</h2>
        <p>
          Flowgrid OS provides an AI operations workspace for UK small
          organisations. This notice covers personal data collected on this
          public website. Data inside customer workspaces is covered by each
          customer&rsquo;s agreement, not this notice.
        </p>
      </section>
      <section>
        <h2>What we collect and why</h2>
        <ul>
          <li>
            <strong>Demo requests:</strong> name, work email, organisation and
            your answers to the form. Used solely to respond to your enquiry
            and arrange the demo (legitimate interest).
          </li>
          <li>
            <strong>Pilot list:</strong> email and workflow interest, used to
            contact you about pilot availability. You can unsubscribe at any
            time.
          </li>
          <li>
            <strong>Technical records:</strong> the page a form was submitted
            from, campaign parameters, and consent version/timestamp, kept for
            accountability.
          </li>
        </ul>
        <p>
          We do not put form content or email addresses into analytics, and we
          ask you not to include sensitive personal data in free-text fields.
        </p>
      </section>
      <section>
        <h2>Retention and your rights</h2>
        <p>
          Enquiry data is kept only as long as needed to handle the enquiry
          and for a defined period afterwards, then deleted. You may request
          access, correction or deletion of your data at any time by emailing{" "}
          <a href="mailto:hello@flowgridos.co.uk">hello@flowgridos.co.uk</a>.
          You may also complain to the ICO.
        </p>
      </section>
      <section>
        <h2>Processors</h2>
        <p>
          Form submissions are delivered to our enquiry-handling systems. The
          current processor list, including destination regions, is available
          on request and will be published here before launch.
        </p>
      </section>
    </LegalPage>
  );
}
