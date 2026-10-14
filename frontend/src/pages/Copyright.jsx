import SEO from '../components/SEO';
import { CARD } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/copyright'];

const LINK =
  'text-primary hover:text-primary-dark font-medium hover:underline transition-colors';

function ExternalLink({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={LINK}>
      {children}
    </a>
  );
}

function Credit({ children }) {
  return (
    <p className="font-mono text-sm text-gray-800 bg-gray-50 border border-gray-200 rounded-md px-4 py-3 mb-4">
      {children}
    </p>
  );
}

export default function Copyright() {
  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/copyright"
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">

        {/* Header */}
        <header className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">Copyright and licensing</h1>
          <p className="mt-1 text-sm text-gray-500">Last updated: 14 October 2026</p>
        </header>

        {/* 1. Summary */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">1. Summary</h2>
          <p className="text-gray-700 leading-relaxed mb-3">
            mergers.fyi brings together its own data and material from others, and each is licensed differently:
          </p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>
              <span className="font-medium">our own data</span> - the structured merger data, analysis and
              commentary we produce - is licensed under CC BY 4.0; and
            </li>
            <li>
              <span className="font-medium">material from others</span> - the ACCC, the Australian Competition
              Tribunal, the Federal Court of Australia, merger parties and other third parties - remains theirs,
              on their own terms.
            </li>
          </ul>
          <p className="text-gray-700 leading-relaxed">
            Before reusing anything, check which of these it falls under. If in doubt, go back to the original
            source.
          </p>
        </section>

        {/* 2. Our data */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">2. Our data</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Copyright &copy; 2026 Nick Twort. The data published by mergers.fyi is licensed under the{' '}
            <ExternalLink href="https://creativecommons.org/licenses/by/4.0/">
              Creative Commons Attribution 4.0 International licence
            </ExternalLink>{' '}
            (CC BY 4.0). This covers:
          </p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>the structured data behind the site, including the JSON files served under{' '}
              <span className="font-mono text-sm">mergers.fyi/data/</span>, the RSS feed and the weekly digest;</li>
            <li>our derived figures and analysis, such as review durations, statistics and Phase 2 timetables;</li>
            <li>material we curate by hand, such as commentary, party groupings, links between related matters,
              and the records of Tribunal and Federal Court reviews; and</li>
            <li>the <span className="font-mono text-sm">fyi.mergers.*</span> records we publish to the AT
              Protocol network.</li>
          </ul>
          <p className="text-gray-700 leading-relaxed mb-4">
            You may copy, share and adapt it for any purpose, including commercially, provided you give
            appropriate credit, link to the licence and say if you made changes. A suitable credit is:
          </p>
          <Credit>Source: mergers.fyi (https://mergers.fyi), licensed under CC BY 4.0.</Credit>
          <p className="text-gray-700 leading-relaxed">
            Much of our data is built from the ACCC&apos;s acquisitions register. If you reuse it, please also
            credit the ACCC (see section 3).
          </p>
        </section>

        {/* 3. Material from the ACCC */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">3. Material from the ACCC</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Matter descriptions, questionnaire questions, determinations, notices and other material written by
            the Australian Competition and Consumer Commission are &copy; Commonwealth of Australia. The ACCC
            publishes material on its website under CC BY 4.0, except for the Commonwealth Coat of Arms, ACCC
            logos, content supplied by third parties, and material where it says otherwise. See the ACCC&apos;s{' '}
            <ExternalLink href="https://www.accc.gov.au/copyright">disclaimer and copyright page</ExternalLink>.
          </p>
          <p className="text-gray-700 leading-relaxed mb-3">
            The ACCC asks that its material be credited as:
          </p>
          <Credit>Source: ACCC &copy; Commonwealth of Australia</Credit>
          <p className="text-gray-700 leading-relaxed mb-3">and, where the material has been modified, for example:</p>
          <Credit>Source: Based on ACCC data</Credit>
          <p className="text-gray-700 leading-relaxed mb-4">
            This site reproduces and reorganises ACCC material from the{' '}
            <ExternalLink href="https://www.accc.gov.au/public-registers/acquisitions-and-mergers-registers/acquisitions-register">
              acquisitions register
            </ExternalLink>
            , and much of what it shows is based on ACCC data in that second sense.
          </p>
          <p className="text-gray-700 leading-relaxed">
            mergers.fyi is an independent, unofficial website. It is not affiliated with, sponsored or endorsed
            by the ACCC, and the ACCC did not create our analysis or commentary. ACCC guidance and the law change
            often: before relying on or republishing anything, check it against the ACCC&apos;s own register.
          </p>
        </section>

        {/* 4. Tribunal and Federal Court material */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">4. Tribunal and Federal Court material</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            For matters under review, this site keeps copies of filings and decisions of the Australian
            Competition Tribunal and judgments of the Federal Court of Australia. Judgments may be reproduced
            in unaltered form, including commercially, provided they are attributed to the court or tribunal
            that made them. Any commentary added to a judgment must be clearly attributed to whoever wrote it,
            not the court. Other material produced by the courts may be reproduced only in unaltered form for
            personal, non-commercial or internal use, unless the court says otherwise. See the Federal
            Court&apos;s{' '}
            <ExternalLink href="https://www.fedcourt.gov.au/copyright">copyright statement</ExternalLink>.
          </p>
          <p className="text-gray-700 leading-relaxed">
            Each document we hold links back to its source. Documents filed by parties to a Tribunal or Federal
            Court proceeding belong to those parties (see section 5).
          </p>
        </section>

        {/* 5. Third-party documents */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">5. Documents written by others</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Many documents on the ACCC register, and some filed with the Tribunal, were written by merger
            parties, their advisers, or others who made submissions. Copyright in those documents stays with
            whoever owns it. They are not covered by CC BY 4.0 - neither ours nor the ACCC&apos;s - and their
            owners&apos; permission may be needed to reuse them.
          </p>
          <p className="text-gray-700 leading-relaxed">
            We keep copies of these documents so that each matter&apos;s record is complete and its links stay
            stable. If you own material on this site and would like it removed, please contact us (see section 6).
          </p>
        </section>

        {/* 6. Contact */}
        <section className={`${CARD} p-8`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">6. Contact</h2>
          <p className="text-gray-700 leading-relaxed">
            For questions about copyright, or to ask for material to be removed, contact us at{' '}
            <a href="mailto:help@mergers.fyi" className={LINK}>
              help@mergers.fyi
            </a>
            . For permission to reuse the ACCC&apos;s, a court&apos;s or a third party&apos;s material, contact
            that owner directly.
          </p>
        </section>

      </div>
    </>
  );
}
