import { useState, useMemo, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { FaSearch } from 'react-icons/fa';
import SEO from '../components/SEO';
import ExternalLinkIcon from '../components/ExternalLinkIcon';
import { GLOSSARY, GLOSSARY_CATEGORIES, GLOSSARY_BY_ID } from '../constants/glossary';

const structuredData = {
  '@context': 'https://schema.org',
  '@type': 'DefinedTermSet',
  name: 'ACCC merger review glossary',
  description:
    'Plain-language definitions of the terms used in Australian merger reviews under the ACCC mandatory and suspensory merger control regime.',
  url: 'https://mergers.fyi/glossary',
  hasDefinedTerm: GLOSSARY.map((entry) => ({
    '@type': 'DefinedTerm',
    '@id': `https://mergers.fyi/glossary#${entry.id}`,
    name: entry.term,
    description: entry.definition,
  })),
};

function matchesQuery(entry, q) {
  if (!q) return true;
  const haystack = [entry.term, entry.abbr, entry.definition, ...(entry.aliases || [])]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return haystack.includes(q);
}

export default function Glossary() {
  const [query, setQuery] = useState('');
  const location = useLocation();
  const [highlightedId, setHighlightedId] = useState(null);
  const hasScrolled = useRef(false);

  const normalisedQuery = query.trim().toLowerCase();

  const grouped = useMemo(() => {
    return GLOSSARY_CATEGORIES.map((category) => ({
      ...category,
      entries: GLOSSARY
        .filter((entry) => entry.category === category.id && matchesQuery(entry, normalisedQuery))
        .sort((a, b) => a.term.localeCompare(b.term)),
    })).filter((category) => category.entries.length > 0);
  }, [normalisedQuery]);

  const totalMatches = grouped.reduce((sum, c) => sum + c.entries.length, 0);

  // Scroll to and briefly highlight a term when arriving via /glossary#<id>.
  useEffect(() => {
    const id = location.hash.replace('#', '');
    if (!id || hasScrolled.current) return;
    const el = document.getElementById(id);
    if (!el) return;
    hasScrolled.current = true;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // Defer the highlight out of the effect body to avoid a cascading render.
    const raf = requestAnimationFrame(() => setHighlightedId(id));
    const timer = setTimeout(() => setHighlightedId(null), 2200);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [location.hash]);

  return (
    <>
      <SEO
        title="Glossary of ACCC merger terms"
        description="Plain-language definitions of the key terms used in Australian merger reviews — notification, Phase 1 and Phase 2, NOCC, waivers, commitments and more."
        url="/glossary"
        structuredData={structuredData}
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 animate-fade-in">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Glossary</h1>
          <p className="text-gray-600 leading-relaxed">
            Plain-language definitions of the terms used across this site and in ACCC merger reviews.
            New to how it all fits together?{' '}
            <Link
              to="/merger-process"
              className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
            >
              Read how ACCC merger review works
            </Link>
            .
          </p>
        </div>

        {/* Search */}
        <div className="sticky top-16 z-10 -mx-4 px-4 py-3 bg-gradient-to-b from-white via-white to-white/0 sm:mx-0 sm:px-0">
          <label htmlFor="glossary-search" className="sr-only">Search terms</label>
          <div className="relative">
            <FaSearch className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" aria-hidden="true" />
            <input
              id="glossary-search"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search terms, e.g. waiver, Phase 2, NOCC…"
              className="w-full pl-10 pr-4 py-2.5 text-sm bg-white border border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 shadow-card focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary/40"
            />
          </div>
          {normalisedQuery && (
            <p className="mt-2 text-xs text-gray-500">
              {totalMatches} {totalMatches === 1 ? 'term' : 'terms'} matching &ldquo;{query.trim()}&rdquo;
            </p>
          )}
        </div>

        {/* Category jump links */}
        {!normalisedQuery && (
          <nav aria-label="Glossary categories" className="mt-4 mb-8 flex flex-wrap gap-2">
            {grouped.map((category) => (
              <a
                key={category.id}
                href={`#cat-${category.id}`}
                className="px-3 py-1.5 text-xs font-medium rounded-full bg-gray-100 text-gray-600 hover:bg-primary/10 hover:text-primary transition-colors"
              >
                {category.label}
              </a>
            ))}
          </nav>
        )}

        {/* Groups */}
        {totalMatches === 0 ? (
          <p className="text-gray-500 py-12 text-center">
            No terms match your search. Try a different word.
          </p>
        ) : (
          <div className="space-y-10 mt-6">
            {grouped.map((category) => (
              <section key={category.id} id={`cat-${category.id}`} aria-labelledby={`cat-${category.id}-heading`}>
                <div className="mb-4">
                  <h2 id={`cat-${category.id}-heading`} className="text-xl font-semibold text-gray-900">
                    {category.label}
                  </h2>
                  <p className="text-sm text-gray-500">{category.blurb}</p>
                </div>

                <dl className="space-y-3">
                  {category.entries.map((entry) => (
                    <div
                      key={entry.id}
                      id={entry.id}
                      className={`scroll-mt-28 bg-white rounded-2xl border p-5 shadow-card transition-all duration-300 ${
                        highlightedId === entry.id
                          ? 'border-primary/50 ring-2 ring-primary/30'
                          : 'border-gray-100'
                      }`}
                    >
                      <dt className="flex items-baseline flex-wrap gap-x-2">
                        <span className="text-base font-semibold text-gray-900">{entry.term}</span>
                        {entry.abbr && entry.abbr !== entry.term && (
                          <span className="text-sm font-medium text-gray-400">({entry.abbr})</span>
                        )}
                      </dt>
                      <dd className="mt-1.5 text-sm text-gray-600 leading-relaxed">{entry.definition}</dd>

                      {(entry.related?.length > 0 || entry.acccUrl) && (
                        <dd className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
                          {entry.related?.map((relId) => {
                            const rel = GLOSSARY_BY_ID[relId];
                            if (!rel) return null;
                            return (
                              <a
                                key={relId}
                                href={`#${relId}`}
                                className="text-xs font-medium text-primary hover:text-primary-dark hover:underline transition-colors"
                              >
                                {rel.term}
                              </a>
                            );
                          })}
                          {entry.acccUrl && (
                            <a
                              href={entry.acccUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs font-medium text-gray-400 hover:text-gray-600 transition-colors"
                            >
                              ACCC guidance
                              <ExternalLinkIcon className="h-3 w-3" />
                              <span className="sr-only">(opens in new tab)</span>
                            </a>
                          )}
                        </dd>
                      )}
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
