import type { Metadata } from "next";
import { LegalPage } from "../legal";

export const metadata: Metadata = {
  title: "Website terms",
  description: "Terms of use for the Flowgrid OS public website.",
  alternates: { canonical: "/terms" },
  robots: { index: false },
};

export default function TermsPage() {
  return (
    <LegalPage title="Website terms of use" updated="16 August 2026">
      <section>
        <h2>Scope</h2>
        <p>
          These terms cover use of this public website. Use of the Flowgrid
          workspace itself is governed by a separate customer agreement
          entered into when a workspace is provisioned.
        </p>
      </section>
      <section>
        <h2>Content</h2>
        <p>
          We work to keep every capability statement on this site accurate to
          the product as it exists today. Content is provided for general
          information and does not form part of any contract; product plans
          may change.
        </p>
      </section>
      <section>
        <h2>Acceptable use</h2>
        <p>
          Don&rsquo;t attempt to probe, disrupt or gain unauthorised access
          to this site or any Flowgrid systems. If you believe you&rsquo;ve
          found a security issue, please report it to{" "}
          <a href="mailto:hello@flowgridos.co.uk">hello@flowgridos.co.uk</a>{" "}
          and we&rsquo;ll respond promptly.
        </p>
      </section>
      <section>
        <h2>Liability</h2>
        <p>
          To the extent permitted by law, we accept no liability for loss
          arising from reliance on this website&rsquo;s content. Nothing in
          these terms limits liability that cannot be limited under law.
        </p>
      </section>
    </LegalPage>
  );
}
