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
    <p className="font-mono text-sm text-gray-800 bg-gray-50 border border-gray-200 rounded-md px-4 py-3 mt-3">
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

        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Our data</h2>
          <p className="text-gray-700 leading-relaxed">
            Copyright &copy; 2026 Nick Twort. The data on this site, including our analysis and commentary, is
            licensed under{' '}
            <ExternalLink href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</ExternalLink>. You may
            reuse it for any purpose, with credit:
          </p>
          <Credit>Source: mergers.fyi (https://mergers.fyi), licensed under CC BY 4.0.</Credit>
        </section>

        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">ACCC material</h2>
          <p className="text-gray-700 leading-relaxed">
            Material from the ACCC&apos;s acquisitions register is &copy; Commonwealth of Australia and published
            under CC BY 4.0, except logos and third-party content (see the ACCC&apos;s{' '}
            <ExternalLink href="https://www.accc.gov.au/copyright">copyright page</ExternalLink>). Credit it as
            below, or as &ldquo;Based on ACCC data&rdquo; if you have changed it. This site is not endorsed by
            the ACCC.
          </p>
          <Credit>Source: ACCC &copy; Commonwealth of Australia</Credit>
        </section>

        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Tribunal and Federal Court material</h2>
          <p className="text-gray-700 leading-relaxed">
            Judgments may be republished unaltered, including commercially, if attributed to the court. Other
            court material is for unaltered personal, non-commercial or internal use. See the Federal
            Court&apos;s{' '}
            <ExternalLink href="https://www.fedcourt.gov.au/copyright">copyright statement</ExternalLink>.
          </p>
        </section>

        <section className={`${CARD} p-8`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Documents written by others</h2>
          <p className="text-gray-700 leading-relaxed">
            Documents written by merger parties and others belong to their authors and are not covered by
            CC BY 4.0. To have your material removed, email{' '}
            <a href="mailto:help@mergers.fyi" className={LINK}>
              help@mergers.fyi
            </a>
            .
          </p>
        </section>

      </div>
    </>
  );
}
