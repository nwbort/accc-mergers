import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router';
import { FaArrowDown, FaArrowUp, FaRedo, FaShareAlt } from 'react-icons/fa';
import ErrorMessage from '../components/ErrorMessage';
import LoadingSpinner from '../components/LoadingSpinner';
import MergedCard from '../components/MergedCard';
import SEO from '../components/SEO';
import ShareButton from '../components/ShareButton';
import { useFetchData } from '../hooks/useFetchData';
import { useTracking } from '../context/TrackingContext';
import { mergedFetch } from '../utils/pageData';
import { STATIC_PAGE_META } from '../utils/pageMeta';

/**
 * Australia Merged — the year in review, at /merged.
 *
 * A deck of tonal cards the reader moves through, in the Android app's
 * Material 3 Expressive language. Everything it says comes from merged.json
 * (scripts/generate/static_data/outputs/merged.py): the page holds the
 * movement, the score and the one card the generator cannot write, and no
 * arithmetic at all.
 *
 * Two deliberate choices about how it moves. There is **no auto-advance**:
 * Wrapped's timed progress bars are a WCAG 2.2.1 failure and are also just
 * annoying when the thing on screen is a number you are reading. And the deck
 * is **one scrolling document** of sections, snapped rather than swapped, so
 * it still reads top to bottom with assistive technology, with the keyboard,
 * and with the scroll wheel, instead of only under a finger.
 */

const PAGE_META = STATIC_PAGE_META['/merged'];

/**
 * Where the reader is: the card filling most of the viewport.
 *
 * The deck scrolls the document rather than a container of its own — the page
 * is inside App's `min-h-screen flex flex-col`, between the navbar and the
 * footer, and a nested scroller would have to fight that. `.merged-snap` on
 * <html> (index.css) is what makes the document snap, for as long as this
 * page is mounted.
 */
function useCurrentCard(count) {
  const { card: param } = useParams();
  // The card in the URL is 1-based, as a reader counts them.
  const opened = useMemo(() => {
    const n = Number.parseInt(param ?? '1', 10);
    return Number.isFinite(n) && n > 0 ? n - 1 : 0;
  }, [param]);

  const [current, setCurrent] = useState(opened);
  const deck = useRef(null);
  // Until the deck has scrolled to the card the URL named, the observer is
  // reporting the top of the page rather than where the reader asked to be,
  // and the URL must not be rewritten from it.
  const landed = useRef(opened === 0);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.add('merged-snap');
    return () => root.classList.remove('merged-snap');
  }, []);

  // A link straight to a card lands on it, once the deck has rendered.
  useEffect(() => {
    if (landed.current || !count) return undefined;
    const section = deck.current?.querySelectorAll('[data-card]')[opened];
    if (!section) return undefined;
    section.scrollIntoView();
    // The smooth scroll is still running; believe the observer again once it
    // has arrived.
    const timer = setTimeout(() => {
      landed.current = true;
    }, 600);
    return () => clearTimeout(timer);
  }, [count, opened]);

  // The card in the URL reflects where the reader has scrolled to, so it is
  // written with history.replaceState rather than a router navigation. Going
  // through the router would be a pathname change, which ScrollToTop answers
  // by scrolling to the top — which moves the reader to the card before,
  // which rewrites the URL again, all the way back to the first card.
  //
  // replaceState and not pushState for the ordinary reason: Back should leave
  // the deck, not walk up through twenty-three of its cards.
  useEffect(() => {
    if (!landed.current) return;
    const here = window.location.pathname;
    // Gone to a merger's page: not ours to rewrite any more.
    if (here !== '/merged' && !here.startsWith('/merged/')) return;
    const path = current === 0 ? '/merged' : `/merged/${current + 1}`;
    if (here !== path) window.history.replaceState(window.history.state, '', path);
  }, [current]);

  useEffect(() => {
    const root = deck.current;
    if (!root || typeof IntersectionObserver === 'undefined') return undefined;
    const sections = Array.from(root.querySelectorAll('[data-card]'));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && entry.intersectionRatio > 0.55) {
            setCurrent(sections.indexOf(entry.target));
          }
        });
      },
      { threshold: [0.55] },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [count]);

  const go = useCallback(
    (index) => {
      const root = deck.current;
      if (!root) return;
      const target = Math.max(0, Math.min(count - 1, index));
      landed.current = true;
      root.querySelectorAll('[data-card]')[target]?.scrollIntoView({ block: 'start' });
      setCurrent(target);
    },
    [count],
  );

  return { current, go, deck };
}

/**
 * The reader's own year, from the follows this browser already holds.
 *
 * The only card the generator cannot write, because its figures never leave
 * the device: merged.json supplies the wording with `{followed}` and
 * `{industries}` left in it, and this fills them.
 */
function YourYear({ card }) {
  const { trackedMergerIds, trackedIndustries } = useTracking();
  const followed = trackedMergerIds?.length || 0;
  const industries = trackedIndustries?.length || 0;
  const heading = followed ? card.heading.replace('{followed}', followed) : card.empty_heading;
  const lines = followed ? card.body || [] : [card.empty_body];

  return (
    <>
      <h2 id="merged-your-year" className="mb-3 text-2xl font-bold leading-tight tracking-tight sm:text-3xl">
        {heading}
      </h2>
      {lines.map((line) => (
        <p key={line} className="mb-3 text-lg font-medium">
          {line}
        </p>
      ))}
      {followed > 0 && industries > 0 && card.industries_line && (
        <p className="mb-3">
          {card.industries_line
            .replace('{industries}', `${industries} ${industries === 1 ? 'industry' : 'industries'}`)
            .replace(
              '{names}',
              trackedIndustries.map((industry) => industry.name || industry.code).join(', '),
            )}
        </p>
      )}
    </>
  );
}

const PILL_BUTTON =
  'inline-flex items-center gap-2.5 rounded-m3-lg px-6 py-4 text-base font-bold ' +
  'transition-[border-radius] duration-[350ms] ease-m3-spring active:rounded-full ' +
  'motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 ' +
  'focus-visible:ring-current focus-visible:ring-offset-2';

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(text).then(
          () => setCopied(true),
          () => setCopied(false),
        );
      }}
      className={`${PILL_BUTTON} mt-2 bg-m3-surface-container-lowest text-m3-on-surface`}
    >
      <FaShareAlt aria-hidden="true" />
      {copied ? 'Copied' : 'Copy to your clipboard'}
    </button>
  );
}

export default function Merged() {
  const [cacheKey, url] = mergedFetch();
  const { data, loading, error } = useFetchData(url, { cacheKey });
  const [answers, setAnswers] = useState({});

  const cards = useMemo(() => data?.cards || [], [data]);
  const { current, go, deck } = useCurrentCard(cards.length);

  const score = useMemo(
    () =>
      cards.filter((card) => card.kind === 'quiz' && answers[card.id] === card.answer).length,
    [cards, answers],
  );

  useEffect(() => {
    function onKey(event) {
      if (event.target instanceof HTMLButtonElement) return;
      const forward = ['ArrowRight', 'ArrowDown', 'PageDown'];
      const back = ['ArrowLeft', 'ArrowUp', 'PageUp'];
      if (forward.includes(event.key)) {
        event.preventDefault();
        go(current + 1);
      } else if (back.includes(event.key)) {
        event.preventDefault();
        go(current - 1);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [current, go]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!cards.length) return <ErrorMessage error={new Error('No year in review to show yet.')} />;

  const total = data.quiz_total || 0;
  const answeredAll = Object.keys(answers).length >= total && total > 0;
  const shareText = (data.share_text || '')
    .replace('{matters}', data.facts?.volume?.matters ?? '')
    .replace('{refused}', data.facts?.outcomes?.refused?.length ?? '')
    .replace('{score}', score)
    .replace('{total}', total)
    .replace('{year}', data.year);
  // shareTargets() appends the URL itself, so the post text is everything
  // above it.
  const sharePost = shareText.split('\n').slice(0, -1).join('\n');

  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/merged"
        image={PAGE_META.image}
        imageAlt={PAGE_META.imageAlt}
      />

      {/* The whole deck is one h1; each card carries its own h2. */}
      <h1 className="sr-only">{`Australia Merged: the ${data.year} year in review`}</h1>

      {/* The progress rail carries its own band from the very top, because the
          navbar above it hides itself on a downward scroll: anchored at top-16
          instead, the strip it left behind would show the previous card
          sliding past. The navbar sits at z-50 and covers this while it is
          there. */}
      <div
        className="fixed inset-x-0 top-0 z-20 flex gap-1 bg-gradient-to-b from-m3-surface-container-low from-80% to-transparent px-4 pb-4 pt-[4.25rem] sm:px-6"
        role="tablist"
        aria-label="Cards"
      >
        {cards.map((card, index) => (
          <button
            key={card.id}
            type="button"
            role="tab"
            aria-selected={index === current}
            aria-label={`Card ${index + 1} of ${cards.length}`}
            onClick={() => go(index)}
            className={`min-w-0 flex-1 rounded-sm transition-[background-color,height] duration-300 ease-m3-emphasized motion-reduce:transition-none ${
              index === current
                ? 'h-1.5 bg-m3-primary'
                : index < current
                  ? 'h-1 bg-[color-mix(in_srgb,#335145_55%,transparent)]'
                  : 'h-1 bg-[color-mix(in_srgb,#2b3530_18%,transparent)]'
            }`}
          />
        ))}
      </div>

      <div ref={deck} className="-mt-16 bg-m3-surface-container-low pt-16 text-m3-on-surface">
        {cards.map((card) => (
          <MergedCard
            key={card.id}
            card={card}
            year={data.year}
            answer={answers[card.id]}
            onAnswer={(key) => setAnswers((prev) => ({ ...prev, [card.id]: key }))}
            slot={
              card.kind === 'personal' ? (
                <YourYear card={card} />
              ) : card.kind === 'closing' ? (
                <>
                  {answeredAll && (
                    <p className="mb-3 text-lg font-medium">{data.score_lines?.[String(score)]}</p>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    <CopyButton text={shareText} />
                    {/* The site's own share menu: LinkedIn, Bluesky, email,
                        or the phone's share sheet. It carries the score as the
                        post text and appends the URL itself. `onDark` because
                        the closing card is a deep fill. */}
                    <ShareButton path="/merged" title={sharePost} onDark />
                  </div>
                </>
              ) : null
            }
            after={
              card.kind === 'closing' ? (
                <button
                  type="button"
                  onClick={() => {
                    setAnswers({});
                    go(0);
                  }}
                  className={`${PILL_BUTTON} mt-6 border border-current/25 bg-transparent text-m3-on-surface`}
                >
                  <FaRedo aria-hidden="true" />
                  Start again
                </button>
              ) : null
            }
          />
        ))}
      </div>

      {/* The app's floating toolbar: where you are, and the way out of here. */}
      <div className="fixed bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-1 rounded-full bg-m3-surface-container-highest p-1.5 shadow-card-hover">
        <button
          type="button"
          onClick={() => go(current - 1)}
          disabled={current === 0}
          aria-label="Previous card"
          className="grid h-10 w-10 place-items-center rounded-full text-m3-on-surface transition-[border-radius] duration-300 ease-m3-spring hover:bg-[color-mix(in_srgb,#2b3530_9%,transparent)] active:rounded-m3-sm disabled:opacity-35 motion-reduce:transition-none"
        >
          <FaArrowUp aria-hidden="true" />
        </button>
        <span className="grid h-10 place-items-center rounded-full bg-m3-primary-container px-4 text-sm font-bold tabular-nums text-m3-on-primary-container">
          {`${score} / ${total}`}
        </span>
        <button
          type="button"
          onClick={() => go(current + 1)}
          disabled={current === cards.length - 1}
          aria-label="Next card"
          className="grid h-10 w-10 place-items-center rounded-full text-m3-on-surface transition-[border-radius] duration-300 ease-m3-spring hover:bg-[color-mix(in_srgb,#2b3530_9%,transparent)] active:rounded-m3-sm disabled:opacity-35 motion-reduce:transition-none"
        >
          <FaArrowDown aria-hidden="true" />
        </button>
      </div>
    </>
  );
}
