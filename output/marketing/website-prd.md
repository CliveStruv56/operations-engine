# Flowgrid OS public website PRD

**Status:** Approved positioning and conversion direction  
**Version:** 1.0 - 16 August 2026  
**Owner:** Product/Founder  
**Product surface:** Public marketing site and lead capture; authenticated application remains separate

## 1. Outcome

Launch a credible, fast public website that helps a qualified visitor understand Flowgrid in under a minute, recognise a relevant workflow, and either book a demo or join the pilot list. The site must not imply that unfinished roadmap capabilities are available or send an unqualified visitor straight into an invite-led application.

### Success measures for the first 90 days

- At least 60% of tracked visitors reach one proof or solution section.
- At least 4% of qualified non-bot sessions start a primary conversion.
- At least 60% of started lead forms complete.
- At least 30% of submitted leads meet the agreed ideal-customer criteria.
- Core Web Vitals pass at the 75th percentile on mobile.
- No critical or serious automated accessibility defects; keyboard journey passes manually.

Targets are starting hypotheses, not forecasts. Review after the first 200 qualified sessions.

## 2. Audience and jobs

### Primary: operations-led small organisations

UK organisations with roughly 3-50 users whose work depends on shared documents, recurring forms, project evidence and management reporting. The buyer may be an owner, operations lead or practice lead.

**Job:** “Help my team reuse what we already know, keep it trustworthy and turn it into work without buying a disconnected tool for every task.”

### Secondary: specialist consultants and delivery teams

Consultancies and intermediaries running multiple community-development or grant-funded engagements.

**Job:** “Give every engagement a consistent operating spine and produce client/funder outputs from live records rather than reconstructing them in Word.”

### Important anxieties

- Will it invent facts or hide where answers came from?
- Can another customer see our data?
- Is this simply a generic chatbot with a new skin?
- How much setup and behaviour change does it require?
- Is the relevant specialist workflow genuinely available?

## 3. Positioning and conversion strategy

### Value proposition

**Headline:** Turn what your organisation knows into work you can trust.

**Subhead:** Flowgrid connects your source documents, confirmed facts and live projects in one workspace - so your team can find cited answers, run repeatable workflows and produce finished, branded outputs.

### Conversion model

Use **Book a demo** as the primary CTA and **Join the pilot list** as the secondary CTA. Do not use “Start free” in v1. The repository contains account signup, but current operating documentation indicates invite-led provisioning and manually enabled modules. A high-intent assisted conversion is more honest and produces better discovery data at this stage.

Primary CTA opens a short scheduling/qualification flow. Secondary CTA opens an inline form. Existing users receive a quiet “Sign in” link in the header.

## 4. Information architecture

### V1 routes

| Route | Purpose | Primary CTA |
| --- | --- | --- |
| `/` | Category, value, proof, workflow and conversion overview | Book a demo |
| `/solutions/groundwork` | Community-led development workflow | Discuss a pilot |
| `/solutions/grantwork` | Grant application and reporting workflow | Discuss a pilot |
| `/platform` | Vault, claims, projects, outputs, governance | Book a demo |
| `/security-and-data` | Plain-English architecture, data flow and substantiated controls | Ask a question |
| `/about` | Why Flowgrid exists and who is behind it | Book a demo |
| `/contact` | Demo/pilot form and contact alternative | Submit request |
| `/privacy`, `/terms`, `/cookies` | Legal and consent documents | None |

Defer pricing until packaging and operational entitlements are reconfirmed. Defer blog/resources until there is a repeatable publishing owner.

## 5. Homepage content specification

### Header

- Wordmark/logo, Platform, Solutions, Security & data, About.
- “Sign in” text link and “Book a demo” primary button.
- Mobile menu operable by keyboard, with focus trap and Escape close.

### Hero

- Headline and subhead above.
- Primary CTA: Book a demo.
- Secondary CTA: Explore the platform.
- Product visual: a composed UI view showing a cited answer beside a source, with a claims status and a project output cue. Use real product UI or clearly labelled representative data; never fabricate customer information.
- Trust line: “Built for UK small organisations and specialist teams.”

### Problem-to-outcome strip

Three concise before/after pairs:

1. Scattered documents → cited answers with a visible source.
2. Repeated re-keying → reusable, reviewed organisational facts.
3. Blank-page reporting → structured outputs assembled from live records.

### How it works

1. **Bring the evidence together.** Add documents and connect the facts your organisation relies on.
2. **Keep work structured.** Use projects, plans and specialist registers instead of rebuilding context in each chat.
3. **Produce and review.** Draft from evidence, check citations and export a useful deliverable.

### Product proof

Use four outcome cards, each paired with a real interface crop or short silent video:

- Ask the vault; open the cited page.
- Confirm a claim once; reuse it across drafts.
- Turn a project into a plan with owned tasks.
- Export a conversation to PDF or a response to editable PowerPoint.

### Solutions

- **Groundwork:** keep community-led development projects moving through stage gates, funding, budget, risks and client reporting.
- **Grantwork:** manage applications, award conditions, impact evidence and monitoring returns in one workflow.
- **Core platform:** for teams that need cited knowledge, controlled facts and repeatable project work without a sector module.

Do not show Tenderhouse or Assurance as “coming soon” until there is an explicit lead-validation strategy and owner.

### Trust and controls

Explain controls in buyer language, then offer technical detail:

- Every tenant-scoped data table is protected by database row-level security.
- Roles and module entitlements limit what users can see and do.
- AI usage and cost are recorded per call.
- Grounded answers link back to the document and page used.
- Outbound/provider data handling is documented on `/security-and-data`; commercial guarantees must match signed provider terms.

Avoid compliance badges or absolute security language without evidence.

### Final CTA

“Bring one repeated workflow. We’ll show you how it fits.”  
Book a 20-minute demo, with a secondary email-only pilot signup.

## 6. Solution page template

Each solution page follows the same decision path:

1. Audience-specific headline and costly current workaround.
2. A single end-to-end workflow diagram.
3. Three outcome sections with product evidence.
4. “What lives in the workspace” capability list.
5. Example deliverables.
6. Trust/control callout.
7. Fit/not-fit qualifier.
8. Pilot CTA.

### Groundwork copy spine

**Headline:** Keep the project record current. Let the client report follow.  
Show: portfolio → five stage gates → budget/funding/risks → monthly report, feasibility study or funding bid → health card.

### Grantwork copy spine

**Headline:** Carry evidence from application to monitoring return.  
Show: funder/application → stages and conditions → impact measures/outcomes → application or monitoring draft.

## 7. Lead capture and signup

### Demo form fields

Ask only what is needed to qualify and respond:

- Work email (required)
- Name (required)
- Organisation (required)
- Which workflow? Core / development projects / grants / not sure (required)
- Team size: 1-4 / 5-14 / 15-49 / 50+ (optional)
- What do you repeatedly need to find, check or produce? (optional, 500 characters)
- Consent checkbox only if marketing consent is separate from responding to the enquiry

Do not ask for phone number, password, documents or detailed sensitive data at this stage. After submit, show an immediate confirmation and send a concise transactional email with next steps.

### Pilot-list form

Email and workflow interest only. Use double opt-in if the address will enter an ongoing marketing list. State frequency and provide unsubscribe.

### Data handling

- Server-side validation and spam protection that does not block keyboard or assistive-technology users.
- Store source page, UTM values, consent version/timestamp and submission timestamp.
- Never put free-text form content or email addresses in analytics events.
- Define retention and deletion handling before launch.
- If using a scheduler or CRM, document the processor and destination region.

## 8. Functional requirements

### Content and CMS

- V1 may use typed content files in the Next.js repository; no CMS is required for infrequent pages.
- All public claims have a content owner, evidence reference and last-reviewed date in a non-public claims file.
- Solution availability is controlled from one content object to prevent contradictory labels.
- Open Graph image, title and description are editable per route.

### Analytics

Track: page viewed, meaningful section viewed, CTA clicked, form started, validation error, form submitted, scheduler completed and outbound sign-in clicked. Record CTA name, page and solution only. Use consent-aware analytics appropriate to the final cookie implementation.

### SEO

- Server-rendered, indexable HTML with a unique title, meta description and canonical URL per page.
- Organisation and WebSite structured data; add SoftwareApplication only when pricing/offer data is accurate enough to maintain.
- XML sitemap, robots rules, favicon and share images.
- Descriptive headings and internal links; important product meaning remains text, not baked into screenshots.
- No generated doorway pages or generic AI-written article programme.

### Accessibility

- Target WCAG 2.2 AA.
- Semantic landmarks and one descriptive H1 per page.
- Visible keyboard focus; no keyboard traps; skip link.
- Minimum 44×44 CSS pixel touch targets where practical.
- Form labels, instructions and errors programmatically associated and summarised.
- Respect reduced motion; video has captions or an equivalent text explanation.
- Product screenshots have useful alt text or are marked decorative when adjacent copy already explains them.
- Contrast checked for the terracotta/Hearth palette in every state.

### Performance and resilience

- Mobile-first responsive layout from 320 px.
- Performance budgets: initial JS <170 KB gzip for content pages, hero media <250 KB, no autoplay video above the fold.
- Targets: LCP ≤2.5 s, INP ≤200 ms, CLS ≤0.1 at the 75th percentile.
- Optimised responsive images, local/subset fonts and no blocking third-party scripts.
- Lead submission is idempotent, gives a useful retry state and has a monitored fallback email address.

## 9. Design direction

Extend the existing Hearth visual language: warm paper/cream ground, dark ink, restrained terracotta accent, editorial display type and highly legible sans-serif body. The website should feel like dependable professional software, not a neon AI template.

- Use generous whitespace and real interface evidence.
- Use diagrams only to explain the evidence-to-output flow.
- Avoid stock photos, floating gradient orbs, generic robot imagery and walls of feature cards.
- Motion is functional: citation opening, claim review and draft assembly; always optional.

## 10. Technical approach

- Add a public route group in the existing Next.js app so `/` no longer redirects unauthenticated visitors to `/login`.
- Keep authenticated `/app` layouts and middleware isolated from public routes.
- Implement public pages as server components; isolate the menu, forms and analytics as small client components.
- Create a server-only lead endpoint with schema validation, rate limiting, idempotency key and adapter interface for the chosen CRM/email destination.
- Add CSP/security headers, HTTPS-only production configuration and secret scanning.
- Preserve the current signup route but do not promote it publicly until onboarding and entitlement provisioning are ready.

## 11. Acceptance criteria

- A first-time target visitor can state what Flowgrid does and identify one relevant outcome after a five-second exposure test.
- Every live capability statement maps to current code or an approved operational guarantee.
- Public pages work without authentication and authenticated application behaviour is unchanged.
- Demo and pilot forms validate, submit once, notify the owner, send confirmation and expose a recoverable error state.
- Full keyboard journey passes at 320 px and desktop; screen-reader form labels/errors are coherent.
- Lighthouse lab runs score ≥90 in Performance, Accessibility, Best Practices and SEO on the homepage and both solution pages, followed by real-user monitoring.
- Search metadata, sitemap, robots, canonical tags, social cards and not-found route are verified in production.
- Analytics events fire once and contain no personal/free-text data.
- Legal copy and processor list are approved before production form collection.

## 12. Delivery slices

1. **Foundation:** public route group, design tokens, header/footer, metadata, analytics consent decision.
2. **Conversion page:** homepage and reusable proof/solution components using representative product imagery.
3. **Depth:** Platform, Groundwork, Grantwork, Security & data, About.
4. **Lead flow:** endpoint, CRM/email adapter, demo and pilot forms, confirmation email, monitoring.
5. **Quality:** content-claim review, accessibility audit, device/browser QA, performance tuning and launch checks.

## 13. Confirmed decisions and remaining inputs

- Primary audience: UK small organisations and the consultants who support them.
- Primary CTA: Book a demo. Secondary CTA: Join the pilot list.
- Public identity: Flowgrid OS, `flowgridos.co.uk`, and the Hearth palette.
- Groundwork and Grantwork: available for pilots. Tenderhouse: not promoted as available.
- Pricing: omitted from the initial public site.

Remaining implementation inputs:

- Confirm who owns lead response and the response-time target.
- Choose scheduler, CRM/email destination and analytics platform.
- Approve privacy wording, retention period and provider/subprocessor facts.
- Supply 3-5 approved, sanitised product screenshots or permission to create a representative demo tenant.

## 14. Research basis

The spec applies established guidance rather than copying competitor page structures:

- Google Search Central recommends indexable text for key information, mobile-friendly pages, HTTPS and strong page experience: https://developers.google.com/search/docs/fundamentals/get-started
- GOV.UK recommends short, direct interface copy, asking only questions needed to deliver the service, and clear transactional follow-up: https://www.gov.uk/service-manual/design/writing-for-user-interfaces and https://www.gov.uk/service-manual/design/form-structure
- GOV.UK accessibility guidance uses WCAG 2.2 AA as the target and stresses keyboard, screen-reader and progressive-enhancement support: https://www.gov.uk/service-manual/technology/accessibility-for-developers-an-introduction
- Core Web Vitals thresholds are reflected in the performance criteria: https://web.dev/articles/vitals
