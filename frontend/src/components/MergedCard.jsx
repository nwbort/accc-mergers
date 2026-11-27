import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router';
import MaterialShape from './MaterialShape';
import { sheetTone } from '../constants/mergedTones';
import { formatDateMedium } from '../utils/dates';

/**
 * One card of the Australia Merged deck.
 *
 * Every card is a tonal sheet on the Material 3 shape scale's hero radius,
 * rendered from whatever `merged.json` says it is. The component holds no
 * figures and no sentences: the generator
 * (scripts/generate/static_data/outputs/merged.py) writes both, so the page
 * and the data can never disagree. Adding a card is a change there, not here;
 * only a *new kind* of card needs a branch below.
 */

/** Markdown inline, so `**bold**` in a generated sentence stays one line. */
const INLINE = { p: ({ children }) => <>{children}</> };

function Prose({ children, className = '' }) {
  return (
    <p className={className}>
      <ReactMarkdown components={INLINE}>{children}</ReactMarkdown>
    </p>
  );
}

function Eyebrow({ card }) {
  if (!card.eyebrow && !card.glyph) return null;
  return (
    <p className="mb-4 flex items-center gap-3 text-sm font-semibold opacity-80">
      {card.glyph && <MaterialShape status={card.glyph} size={36} decorative />}
      <span>{card.eyebrow}</span>
    </p>
  );
}

function Stat({ card }) {
  if (card.stat === undefined || card.stat === null) return null;
  return (
    <span className="mb-1 block text-[clamp(3rem,16vw,6rem)] font-extrabold leading-[0.88] tracking-[-0.04em] tabular-nums">
      {card.stat}
      {card.stat_suffix}
    </span>
  );
}

function Figures({ figures }) {
  if (!figures?.length) return null;
  return (
    <div className="my-4 flex flex-wrap gap-2.5">
      {figures.map((figure) => (
        <div
          key={figure.label}
          className="min-w-0 rounded-m3-md bg-[color-mix(in_srgb,currentColor_9%,transparent)] px-4 py-3"
        >
          <span className="block text-2xl font-bold leading-tight tracking-tight tabular-nums sm:text-3xl">
            {figure.value}
            {figure.suffix}
          </span>
          <span className="block text-xs font-semibold opacity-80">{figure.label}</span>
        </div>
      ))}
    </div>
  );
}

function Body({ card }) {
  return (
    <>
      {card.lede && <Prose className="mb-3 text-lg font-medium sm:text-xl">{card.lede}</Prose>}
      {(card.body || []).map((paragraph) => (
        <Prose key={paragraph} className="mb-3 max-w-prose last:mb-0">
          {paragraph}
        </Prose>
      ))}
      {card.note && (
        <p className="mt-4 max-w-prose text-xs leading-relaxed opacity-75">{card.note}</p>
      )}
    </>
  );
}

/** A matter's name, linked to its page where the card names the matter. */
function MergerLink({ id, children }) {
  if (!id) return children;
  return (
    <Link
      to={`/mergers/${id}`}
      className="decoration-current/40 underline-offset-4 hover:underline"
    >
      {children}
    </Link>
  );
}

function Rows({ rows }) {
  if (!rows?.length) return null;
  return (
    <ul className="my-3 flex list-none flex-col gap-2.5 p-0">
      {rows.map((row) => (
        <li key={row.text} className="flex min-w-0 items-start gap-3">
          <MaterialShape status={row.glyph} size={28} decorative className="mt-0.5" />
          <span className="min-w-0">
            <ReactMarkdown components={INLINE}>{row.text}</ReactMarkdown>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** "09 Nov – 19 Nov 2026": a hearing that sits over several days, said once. */
function dateRange(start, end) {
  const from = formatDateMedium(start);
  const to = formatDateMedium(end);
  const year = to.slice(-4);
  return `${from.endsWith(year) ? from.slice(0, -5) : from} – ${to}`;
}

function Timeline({ entries }) {
  const dated = (entries || []).filter((entry) => entry.date);
  if (!dated.length) return null;
  return (
    <ol className="my-3 flex list-none flex-col gap-2 p-0">
      {dated.map((entry) => (
        <li key={entry.label} className="grid grid-cols-[auto_1fr] items-baseline gap-3">
          <span className="whitespace-nowrap text-xs font-semibold tabular-nums opacity-70">
            {entry.end_date ? dateRange(entry.date, entry.end_date) : formatDateMedium(entry.date)}
          </span>
          <span className="min-w-0">
            <ReactMarkdown components={INLINE}>{entry.label}</ReactMarkdown>
          </span>
        </li>
      ))}
    </ol>
  );
}

/**
 * The monthly inflow. A canvas would buy nothing here — it is eleven bars —
 * so it is plain elements with an sr-only table beside them, the same pairing
 * the site's real charts use (docs/accessibility.md).
 */
function Months({ months, year }) {
  if (!months?.length) return null;
  const peak = Math.max(...months.map((month) => month.count));
  return (
    <>
      <div className="my-4 flex h-44 items-end gap-1" aria-hidden="true">
        {months.map((month) => (
          <div key={month.month} className="flex h-full min-w-0 flex-1 flex-col justify-end gap-1.5">
            <div
              className={`rounded-t-m3-xs transition-[height] duration-700 ease-m3-spring motion-reduce:transition-none ${
                month.partial
                  // Hatched, not just short: the month is still running, and a
                  // short bar would read as a collapse in filings.
                  ? 'bg-[repeating-linear-gradient(135deg,#335145_0_5px,color-mix(in_srgb,#335145_35%,transparent)_5px_10px)]'
                  : 'bg-m3-primary'
              }`}
              style={{ height: `${(month.count / peak) * 100}%` }}
            />
            <div className="text-center text-[0.6875rem] font-semibold opacity-70">{month.label}</div>
          </div>
        ))}
      </div>
      <table className="sr-only">
        <caption>{`Matters filed per month, ${year}`}</caption>
        <thead>
          <tr>
            <th scope="col">Month</th>
            <th scope="col">Matters</th>
          </tr>
        </thead>
        <tbody>
          {months.map((month) => (
            <tr key={month.month}>
              <th scope="row">{`${month.name} ${year}`}</th>
              <td>{month.partial ? `${month.count} (month incomplete)` : month.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

/**
 * A review's clock, one tick per business day: green to the statutory limit,
 * red past it, with the limit marked.
 */
function Rail({ rail }) {
  if (!rail?.total) return null;
  const markAt = (rail.mark / rail.total) * 100;
  const ticks = Array.from({ length: rail.total }, (_, index) => index + 1);
  return (
    <div className="relative my-4">
      <div className="relative flex h-10 gap-0.5" aria-hidden="true">
        {ticks.map((day) => (
          <i
            key={day}
            className={`min-w-0 flex-1 rounded-sm ${
              day > rail.used
                ? 'bg-[color-mix(in_srgb,currentColor_16%,transparent)]'
                : day > rail.statutory
                  ? 'bg-red-700'
                  : 'bg-emerald-700'
            }`}
          />
        ))}
        <span
          className="absolute -top-1.5 -bottom-1.5 w-0.5 rounded-sm bg-current"
          style={{ left: `${markAt}%` }}
        />
      </div>
      <div className="relative mt-2 h-5 text-xs font-semibold opacity-80">
        <span className="absolute left-0 top-0 whitespace-nowrap">{rail.start_label}</span>
        <span
          className="absolute top-0 -translate-x-1/2 whitespace-nowrap opacity-100"
          style={{ left: `${markAt}%` }}
        >
          {rail.mark_label}
        </span>
        <span className="absolute right-0 top-0 whitespace-nowrap">{rail.end_label}</span>
      </div>
      <p className="sr-only">
        {`${rail.used} of ${rail.total} business days used, against a statutory ${rail.statutory}.`}
      </p>
    </div>
  );
}

/** The M3 pill button that squares off under the finger and springs back. */
const PILL =
  'w-full rounded-full px-5 py-3.5 text-left text-base font-semibold ' +
  'transition-[border-radius,background-color,color,opacity] duration-[350ms] ' +
  'ease-m3-spring active:rounded-m3-sm motion-reduce:transition-none ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-m3-primary focus-visible:ring-offset-2';

function Reveal({ card }) {
  const [shown, setShown] = useState(false);
  return (
    <>
      {!shown && (
        <button
          type="button"
          onClick={() => setShown(true)}
          className={`${PILL} max-w-sm bg-m3-secondary-container text-m3-on-secondary-container hover:brightness-[0.97]`}
        >
          {card.prompt}
        </button>
      )}
      {shown && (
        <div className="animate-m3-rise rounded-m3-lg bg-m3-surface-container-lowest p-5 text-m3-on-surface motion-reduce:animate-none">
          <p className="mb-2 flex items-center gap-2.5 text-lg font-bold tracking-tight">
            <MaterialShape status={card.glyph} size={32} decorative />
            {card.answer}
          </p>
          <Body card={card} />
        </div>
      )}
    </>
  );
}

function Quiz({ card, answered, onAnswer }) {
  const picked = answered;
  const done = picked != null;
  return (
    <>
      <h2
        id={`merged-${card.id}`}
        className="mb-4 text-xl font-bold leading-tight tracking-tight text-balance sm:text-2xl"
      >
        {card.question}
      </h2>
      <div className="flex flex-col gap-2">
        {card.options.map((option) => {
          const isAnswer = option.key === card.answer;
          const isPick = option.key === picked;
          const state = !done
            ? 'bg-m3-secondary-container text-m3-on-secondary-container hover:brightness-[0.97]'
            : isAnswer
              ? 'rounded-m3-lg bg-emerald-700 text-white'
              : isPick
                ? 'rounded-m3-lg bg-red-700 text-white'
                : 'bg-m3-secondary-container text-m3-on-secondary-container opacity-45';
          return (
            <button
              key={option.key}
              type="button"
              disabled={done}
              aria-pressed={done ? isPick : undefined}
              onClick={() => onAnswer(option.key)}
              className={`${PILL} flex items-center gap-3 disabled:cursor-default ${state}`}
            >
              {done && (isAnswer || isPick) && (
                // On a filled pill the tile inverts: white shape, the
                // outcome's colour as the glyph, so it reads against the fill
                // instead of disappearing into it.
                <span className="animate-m3-pop motion-reduce:animate-none">
                  <MaterialShape
                    status={isAnswer ? 'Approved' : 'Not approved'}
                    size={26}
                    decorative
                    className={isAnswer ? '!bg-white !text-emerald-700' : '!bg-white !text-red-700'}
                  />
                </span>
              )}
              <span className="min-w-0">{option.label}</span>
            </button>
          );
        })}
      </div>
      {done && (
        <div className="mt-4 animate-m3-rise rounded-m3-lg bg-m3-surface-container-lowest p-5 text-m3-on-surface motion-reduce:animate-none">
          <p className="mb-2 flex items-center gap-2.5 text-lg font-bold tracking-tight">
            <MaterialShape
              status={picked === card.answer ? 'Approved' : 'Not approved'}
              size={32}
              decorative
            />
            {picked === card.answer ? 'Correct' : 'Not quite'}
          </p>
          <Body card={card} />
        </div>
      )}
    </>
  );
}

export default function MergedCard({ card, year, answer, onAnswer, slot }) {
  return (
    <section
      data-card
      aria-labelledby={`merged-${card.id}`}
      // items-center, and an article sized to its content: a card that fits
      // sits in the middle of the viewport, and one that doesn't starts at the
      // top of its section instead of being centred in a section that grew.
      //
      // No scroll-mt here: `.merged-snap` sets scroll-padding-top on the
      // document (index.css), and a margin as well would land every card a
      // second navbar's height down the page.
      className="flex min-h-[calc(100svh-4rem)] snap-start items-center px-4 pb-24 pt-14 sm:px-6"
    >
      <article
        className={`mx-auto w-full min-w-0 max-w-2xl rounded-m3-xl p-6 sm:p-10 ${sheetTone(card.tone)}`}
      >
        <div className="animate-m3-rise motion-reduce:animate-none">
          <Eyebrow card={card} />
          <Stat card={card} />

          {card.kind === 'quiz' ? (
            <Quiz card={card} answered={answer} onAnswer={onAnswer} />
          ) : (
            <>
              {card.heading && (
                <h2
                  id={`merged-${card.id}`}
                  className={`mb-3 font-bold leading-tight tracking-tight text-balance ${
                    card.kind === 'opening' || card.kind === 'closing'
                      ? 'text-[clamp(2.25rem,9vw,3.5rem)] leading-[0.98]'
                      : 'text-2xl sm:text-3xl'
                  }`}
                >
                  <MergerLink id={card.merger_id}>{card.heading}</MergerLink>
                </h2>
              )}
              {card.kind === 'months' && <Months months={card.months} year={year} />}
              {card.kind === 'rail' && <Rail rail={card.rail} />}
              {card.kind === 'rows' && <Rows rows={card.rows} />}
              {card.kind === 'timeline' && <Timeline entries={card.timeline} />}
              <Figures figures={card.figures} />
              {card.kind === 'reveal' ? <Reveal card={card} /> : <Body card={card} />}
              {slot}
            </>
          )}
        </div>
      </article>
    </section>
  );
}
