import { Link } from 'react-router-dom';
import { FaArrowRight } from 'react-icons/fa';
import SEO from '../components/SEO';
import GlossaryTerm from '../components/GlossaryTerm';

const structuredData = {
  '@context': 'https://schema.org',
  '@type': 'Article',
  headline: 'How ACCC merger review works',
  description:
    'A plain-language walkthrough of how the ACCC reviews mergers under Australia’s mandatory and suspensory merger control regime — from notification through Phase 1, Phase 2 and beyond.',
  about: 'Australian merger control regime',
  url: 'https://mergers.fyi/merger-process',
  publisher: {
    '@type': 'Organization',
    name: 'Australian Merger Tracker',
    url: 'https://mergers.fyi',
  },
};

// The headline stages, used for the "at a glance" stepper.
const STAGES = [
  {
    n: 1,
    termId: 'notification',
    title: 'Notification',
    timing: 'Clock starts',
    body: 'The parties lodge a notification. The deal is now suspensory — it cannot complete until the ACCC approves it.',
  },
  {
    n: 2,
    termId: 'phase-1',
    title: 'Phase 1 review',
    timing: 'Up to 30 business days',
    body: 'A first-pass review. Most deals are approved here; the ACCC can also accept commitments or send the deal to Phase 2.',
  },
  {
    n: 3,
    termId: 'phase-2',
    title: 'Phase 2 review',
    timing: 'Up to 90 business days',
    body: 'An in-depth review for deals that may substantially lessen competition, including a Notice of Competition Concerns.',
  },
  {
    n: 4,
    termId: 'public-benefit',
    title: 'Public benefit',
    timing: 'Optional',
    body: 'If a deal is refused, parties may still seek approval on the basis that it delivers a net public benefit.',
  },
];

function Stage({ stage, isLast }) {
  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      {!isLast && (
        <span className="absolute left-4 top-9 -ml-px h-full w-0.5 bg-gray-200" aria-hidden="true" />
      )}
      <span className="relative z-10 flex h-8 w-8 flex-none items-center justify-center rounded-full bg-primary text-sm font-semibold text-white">
        {stage.n}
      </span>
      <div className="pt-0.5">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <h3 className="text-base font-semibold text-gray-900">
            <GlossaryTerm id={stage.termId}>{stage.title}</GlossaryTerm>
          </h3>
          <span className="text-xs font-medium text-gray-400">{stage.timing}</span>
        </div>
        <p className="mt-1 text-sm text-gray-600 leading-relaxed">{stage.body}</p>
      </div>
    </li>
  );
}

function Section({ title, children }) {
  return (
    <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 sm:p-8">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">{title}</h2>
      <div className="space-y-4 text-gray-700 leading-relaxed">{children}</div>
    </section>
  );
}

export default function MergerProcess() {
  return (
    <>
      <SEO
        title="How ACCC merger review works"
        description="A plain-language walkthrough of Australia’s mandatory merger control regime — notification, Phase 1 and Phase 2 reviews, Notices of Competition Concerns, waivers, commitments and the public benefit test."
        url="/merger-process"
        structuredData={structuredData}
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 animate-fade-in">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">How ACCC merger review works</h1>
          <p className="text-gray-600 leading-relaxed">
            Since 1 January 2026, Australia has a{' '}
            <GlossaryTerm id="merger-control-regime">mandatory and suspensory</GlossaryTerm>{' '}
            merger control regime. Larger acquisitions must be cleared by the{' '}
            <GlossaryTerm id="accc">ACCC</GlossaryTerm> before they can complete. This page walks
            through the journey from start to finish. Hover over any{' '}
            <span className="border-b border-dotted border-primary/50 text-primary">underlined term</span>{' '}
            for a quick definition, or browse the{' '}
            <Link
              to="/glossary"
              className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
            >
              full glossary
            </Link>
            .
          </p>
        </div>

        {/* At a glance stepper */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 sm:p-8 mb-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400 mb-5">
            The journey at a glance
          </h2>
          <ol className="list-none">
            {STAGES.map((stage, i) => (
              <Stage key={stage.n} stage={stage} isLast={i === STAGES.length - 1} />
            ))}
          </ol>
        </div>

        <div className="space-y-6">
          {/* 1. Does the deal need notifying? */}
          <Section title="1. Does the deal need to be notified?">
            <p>
              The regime only bites once a deal is big enough. An acquisition is a{' '}
              <GlossaryTerm id="notifiable-acquisition">notifiable acquisition</GlossaryTerm>{' '}
              when it meets the{' '}
              <GlossaryTerm id="notification-thresholds">notification thresholds</GlossaryTerm>{' '}
              — most notably a combined Australian turnover of the merger parties of at least
              $200 million, plus further target-based and concentration limbs.
            </p>
            <p>
              Where a deal technically meets the thresholds but clearly raises no concerns, parties
              can ask for a{' '}
              <GlossaryTerm id="notification-waiver">notification waiver</GlossaryTerm> — a faster
              path that exempts that specific deal from the obligation to notify. Many matters on
              this site are waiver decisions rather than full reviews.
            </p>
          </Section>

          {/* 2. Lodging the notification */}
          <Section title="2. Lodging the notification">
            <p>
              Parties often start with{' '}
              <GlossaryTerm id="pre-notification">pre-notification engagement</GlossaryTerm> to
              agree the scope of information the ACCC needs. The statutory clock only starts once a
              valid <GlossaryTerm id="notification">notification</GlossaryTerm> is accepted, at
              which point the deal is suspensory and the matter appears on the{' '}
              <GlossaryTerm id="acquisitions-register">Acquisitions Register</GlossaryTerm>.
            </p>
            <p className="text-sm text-gray-500">
              Timeframes are counted in{' '}
              <GlossaryTerm id="business-day">business days</GlossaryTerm>, which exclude weekends,
              ACT public holidays, and the period from 23 December to 10 January.
            </p>
          </Section>

          {/* 3. Phase 1 */}
          <Section title="3. Phase 1 — the first-pass review">
            <p>
              <GlossaryTerm id="phase-1">Phase 1</GlossaryTerm> runs for up to 30 business days. The
              ACCC applies the{' '}
              <GlossaryTerm id="slc">substantial lessening of competition</GlossaryTerm> test: it
              must approve the deal unless it is satisfied the acquisition would, or would be likely
              to, substantially lessen competition in any market.
            </p>
            <p>From day 15, Phase 1 can end in one of three ways:</p>
            <ul className="space-y-2">
              <li className="flex gap-2">
                <FaArrowRight className="mt-1 h-3 w-3 flex-none text-primary" aria-hidden="true" />
                <span>
                  <GlossaryTerm id="approved">Approved</GlossaryTerm> — the deal is cleared and can
                  proceed.
                </span>
              </li>
              <li className="flex gap-2">
                <FaArrowRight className="mt-1 h-3 w-3 flex-none text-primary" aria-hidden="true" />
                <span>
                  Approved subject to{' '}
                  <GlossaryTerm id="commitments">commitments</GlossaryTerm> — concerns are resolved
                  by court-enforceable undertakings (offered by day 20).
                </span>
              </li>
              <li className="flex gap-2">
                <FaArrowRight className="mt-1 h-3 w-3 flex-none text-primary" aria-hidden="true" />
                <span>
                  <GlossaryTerm id="referred-to-phase-2">Referred to Phase 2</GlossaryTerm> — the
                  deal needs a closer look.
                </span>
              </li>
            </ul>
          </Section>

          {/* 4. Phase 2 */}
          <Section title="4. Phase 2 — the in-depth review">
            <p>
              <GlossaryTerm id="phase-2">Phase 2</GlossaryTerm> is reserved for deals that may
              substantially lessen competition and runs for up to 90 business days. By day 25 the
              ACCC issues a{' '}
              <GlossaryTerm id="nocc">Notice of Competition Concerns</GlossaryTerm> setting out its
              preliminary concerns, and the parties have 25 business days to respond. The parties can
              again offer <GlossaryTerm id="commitments">commitments</GlossaryTerm> (by day 60).
              Phase 2 ends in an approval or a refusal.
            </p>
          </Section>

          {/* 5. Public benefit */}
          <Section title="5. The public benefit safety net">
            <p>
              Even if the ACCC decides a deal cannot proceed on competition grounds, the parties can
              lodge a{' '}
              <GlossaryTerm id="public-benefit">public benefit application</GlossaryTerm>, asking the
              ACCC to approve it anyway because the benefits to the public outweigh the harm to
              competition. This optional stage is only available after a deal has otherwise been
              refused.
            </p>
          </Section>

          {/* 6. The outcome */}
          <Section title="6. The outcome">
            <p>
              The ACCC records its decision in a published{' '}
              <GlossaryTerm id="determination">determination</GlossaryTerm>, with reasons. A deal is
              either <GlossaryTerm id="approved">approved</GlossaryTerm> (sometimes with commitments)
              or <GlossaryTerm id="refused">not approved</GlossaryTerm>. Throughout the review you
              will see a matter move through the{' '}
              <GlossaryTerm id="under-assessment">under assessment</GlossaryTerm> and{' '}
              <GlossaryTerm id="assessment-completed">assessment completed</GlossaryTerm> statuses
              shown on the badges across this site.
            </p>
            <p>
              A party unhappy with a determination can seek a limited merits review by the{' '}
              <GlossaryTerm id="tribunal">Australian Competition Tribunal</GlossaryTerm>.
            </p>
          </Section>
        </div>

        {/* CTA */}
        <div className="mt-8 rounded-2xl border border-primary/15 bg-primary/5 p-6 sm:p-8 text-center">
          <h2 className="text-lg font-semibold text-gray-900">See it in practice</h2>
          <p className="mt-1.5 text-sm text-gray-600">
            Browse real matters moving through these stages, or look up any term.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-3">
            <Link
              to="/mergers"
              className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-white shadow-card transition-colors hover:bg-primary-dark"
            >
              Browse mergers
              <FaArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
            <Link
              to="/glossary"
              className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-card transition-colors hover:bg-gray-50"
            >
              Open the glossary
            </Link>
          </div>
        </div>

        <p className="mt-8 text-xs text-gray-400 leading-relaxed text-center">
          This page is a general explainer, not legal advice. For official guidance see the{' '}
          <a
            href="https://www.accc.gov.au/business/mergers-and-acquisitions/merger-control-regime"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-500 hover:text-gray-700 hover:underline transition-colors"
          >
            ACCC merger control regime
          </a>{' '}
          pages.
        </p>
      </div>
    </>
  );
}
