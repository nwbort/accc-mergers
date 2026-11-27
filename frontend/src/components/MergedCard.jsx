import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router';
import MaterialShape from './MaterialShape';
import { sheetTone } from '../constants/mergedTones';
import { useCountUp, useEntrance, useRailFill } from '../hooks/useEntrance';
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
  // Hooks run before the early return, so the card without a figure still
  // calls them; `target` is 0 there and nothing is rendered.
  const target = typeof card.stat === 'number' ? card.stat : 0;
  // Count to the figure's own precision: 99.7 counts in tenths, 896 in whole
  // matters. tabular-nums keeps the digits from jittering on the way up.
  const decimals = String(card.stat ?? '').split('.')[1]?.length ?? 0;
  const [ref, shown] = useCountUp(target);

  if (card.stat === undefined || card.stat === null) return null;
  return (
    <span
      ref={ref}
      className="mb-1 block text-[clamp(3rem,16vw,6rem)] font-extrabold leading-[0.88] tracking-[-0.04em] tabular-nums"
    >
      {shown.toFixed(decimals)}
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
      {/* `lede` sets a card up and `coda` closes it — "Almost.", "An
          extension is the tell." Same treatment, opposite ends of the body,
          and the generator picks which one a line is. */}
      {card.coda && <Prose className="mt-4 text-lg font-medium sm:text-xl">{card.coda}</Prose>}
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
    // The grid is the list, not each row: with a grid per row every date
    // column sized itself, and a nine-day hearing's range pushed its own row
    // out of line with the rest.
    <ol className="my-3 grid list-none grid-cols-[max-content_1fr] gap-x-3 gap-y-2 p-0">
      {dated.map((entry) => (
        <li key={entry.label} className="col-span-2 grid grid-cols-subgrid items-baseline">
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
 * A row of bars with a data table beside it. A canvas would buy nothing at
 * this size — eleven months, seven weekdays — so these are plain elements
 * paired with an `sr-only` table, the same pairing the site's real charts use
 * (docs/accessibility.md).
 *
 * Each bar is `{key, label, value, row, fill}`: `row` is how the table names
 * it, `fill` the class it wears where it isn't the ordinary one.
 */
function Bars({ bars, caption, unit, height = 'h-44' }) {
  const [ref, entered] = useEntrance();
  if (!bars?.length) return null;
  const peak = Math.max(...bars.map((bar) => bar.value));
  return (
    <>
      <div ref={ref} className={`my-4 flex items-end gap-1 ${height}`} aria-hidden="true">
        {bars.map((bar) => (
          <div key={bar.key} className="flex h-full min-w-0 flex-1 flex-col justify-end gap-1.5">
            <div
              className={`rounded-t-m3-xs transition-[height] duration-700 ease-m3-spring motion-reduce:transition-none ${bar.fill || 'bg-m3-primary'}`}
              style={{
                // Drawn at nothing until the chart is in view, so the CSS
                // transition has somewhere to grow from. `entered` is true from
                // the first render wherever the animation won't run, so the
                // bars are never left flat. A real but tiny value keeps a
                // sliver rather than vanishing — the exact count is in the
                // table, which is where the precision lives.
                height: entered
                  ? bar.value > 0
                    ? `max(2px, ${(bar.value / peak) * 100}%)`
                    : '0%'
                  : '0%',
              }}
            />
            <div className="text-center text-[0.6875rem] font-semibold opacity-70">{bar.label}</div>
          </div>
        ))}
      </div>
      <div className="sr-only">
        <table>
          <caption>{caption}</caption>
          <thead>
            <tr>
              <th scope="col">{unit}</th>
              <th scope="col">Matters</th>
            </tr>
          </thead>
          <tbody>
            {bars.map((bar) => (
              <tr key={bar.key}>
                <th scope="row">{bar.row}</th>
                <td>{bar.cell ?? bar.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

const PARTIAL_FILL =
  'bg-[repeating-linear-gradient(135deg,#335145_0_5px,color-mix(in_srgb,#335145_35%,transparent)_5px_10px)]';

/** The year's inflow, month by month. */
function Months({ months, year }) {
  return (
    <Bars
      caption={`Matters filed per month, ${year}`}
      unit="Month"
      bars={(months || []).map((month) => ({
        key: month.month,
        label: month.label,
        value: month.count,
        row: `${month.name} ${year}`,
        cell: month.partial ? `${month.count} (month incomplete)` : month.count,
        // Hatched, not just short: the month is still running, and a short
        // bar would read as a collapse in filings.
        fill: month.partial ? PARTIAL_FILL : undefined,
      }))}
    />
  );
}

/**
 * The week the busiest day sits in. One record day means little without an
 * ordinary one beside it — and the weekend bars are slivers on purpose,
 * because that is the finding.
 */
function Weekdays({ weekdays, year }) {
  return (
    <Bars
      height="h-28"
      caption={`Matters filed by day of the week, ${year}`}
      unit="Day"
      bars={(weekdays || []).map((day) => ({
        key: day.day,
        label: day.short,
        value: day.count,
        row: day.day,
        fill: day.weekend ? 'bg-m3-outline' : undefined,
      }))}
    />
  );
}

/**
 * A ranking as horizontal bars, each one drawing after the one above it.
 *
 * The stagger is the point: four bars arriving together is a chart, four
 * arriving in order is a countdown, and the order is what the card is about.
 * Lengths are relative to the longest, so the leader fills the width and the
 * rest are read against it.
 */
function Ranking({ ranking, unit, caption }) {
  const [ref, entered] = useEntrance();
  if (!ranking?.length) return null;
  const peak = Math.max(...ranking.map((row) => row.value));
  return (
    <>
      <ol ref={ref} className="my-4 flex list-none flex-col gap-3 p-0" aria-hidden="true">
        {ranking.map((row, index) => (
          <li key={row.label} className="min-w-0">
            <div className="mb-1 flex items-baseline justify-between gap-3 text-sm font-semibold">
              <span className="min-w-0 truncate">{row.label}</span>
              <span className="flex-shrink-0 tabular-nums">{row.value}</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-[color-mix(in_srgb,currentColor_12%,transparent)]">
              <div
                className="h-full rounded-full bg-m3-primary transition-[width] duration-500 ease-m3-emphasized motion-reduce:transition-none"
                style={{
                  width: entered ? `${(row.value / peak) * 100}%` : '0%',
                  // Each bar waits for the one above it to finish.
                  transitionDelay: entered ? `${index * 420}ms` : '0ms',
                }}
              />
            </div>
          </li>
        ))}
      </ol>
      <div className="sr-only">
        <table>
          <caption>{caption}</caption>
          <thead>
            <tr>
              <th scope="col">{unit}</th>
              <th scope="col">Matters</th>
            </tr>
          </thead>
          <tbody>
            {ranking.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                <td>{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/**
 * A review's clock, one tick per business day: green to the statutory limit,
 * red past it, with the limit marked.
 */
function Rail({ rail }) {
  // Hooks before the early return: a card without a rail still calls them.
  const [ref, frame] = useRailFill({
    used: rail?.used ?? 0,
    total: rail?.total ?? 0,
    statutory: rail?.statutory ?? 0,
  });
  if (!rail?.total) return null;

  // The rail is as wide as the clock it is drawing, so while that clock grows
  // the marker slides left and the ticks squeeze — which is the overrun made
  // visible rather than just coloured.
  const span = Math.max(1, frame.total);
  const markAt = (rail.mark / span) * 100;
  const ticks = Array.from({ length: Math.round(frame.total) }, (_, index) => index + 1);
  return (
    <div className="relative my-4">
      <div ref={ref} className="relative flex h-10 gap-0.5" aria-hidden="true">
        {ticks.map((day) => (
          <i
            key={day}
            className={`min-w-0 flex-1 rounded-sm ${
              day > frame.filled
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
        {/* Centred on the marker, except near either end, where a centred
            label would hang off the card. While a growing rail is still only
            its clock wide the marker sits at 100%, which is exactly that
            case. */}
        <span
          className="absolute top-0 whitespace-nowrap opacity-100"
          style={
            markAt >= 85
              ? { right: 0 }
              : markAt <= 15
                ? { left: 0 }
                : { left: `${markAt}%`, transform: 'translateX(-50%)' }
          }
        >
          {rail.mark_label}
        </span>
        {/* Held back until the rail has actually grown: while it is still
            only the statutory clock wide, the end label sits on top of the
            marker that is also at its far right. */}
        {(rail.total <= rail.statutory || Math.round(frame.total) > rail.statutory) && (
          <span className="absolute right-0 top-0 whitespace-nowrap">
            {Math.round(frame.total) === rail.total
              ? rail.end_label
              : `Day ${Math.round(frame.total)}`}
          </span>
        )}
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

function Quiz({ card, year, answered, onAnswer }) {
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
          <p
            className={`flex items-center gap-2.5 text-lg font-bold tracking-tight ${
              card.body?.length || card.weekdays ? 'mb-2' : ''
            }`}
          >
            <MaterialShape
              status={picked === card.answer ? 'Approved' : 'Not approved'}
              size={32}
              decorative
            />
            {picked === card.answer ? 'Correct' : 'Not quite'}
          </p>
          <Body card={card} />
          {card.weekdays && <Weekdays weekdays={card.weekdays} year={year} />}
        </div>
      )}
    </>
  );
}

export default function MergedCard({ card, year, answer, onAnswer, slot, after }) {
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
      className="flex min-h-[calc(100svh-4rem)] snap-start flex-col items-center justify-center px-4 pb-24 pt-14 sm:px-6"
    >
      <article
        className={`mx-auto w-full min-w-0 max-w-2xl rounded-m3-xl p-6 sm:p-10 ${sheetTone(card.tone)}`}
      >
        <div className="animate-m3-rise motion-reduce:animate-none">
          <Eyebrow card={card} />
          <Stat card={card} />

          {card.kind === 'quiz' ? (
            <Quiz card={card} year={year} answered={answer} onAnswer={onAnswer} />
          ) : (
            <>
              {card.heading && card.kind !== 'personal' && (
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
              {card.kind === 'ranking' && (
                <Ranking
                  ranking={card.ranking}
                  unit={card.ranking_unit}
                  caption={`${card.eyebrow}, ${year}`}
                />
              )}
              {card.kind === 'timeline' && <Timeline entries={card.timeline} />}
              <Figures figures={card.figures} />
              {/* The personal card has no generated body: its heading and
                  wording are templates the page fills from this browser's own
                  follows, so rendering `card` here would print the `{followed}`
                  placeholder above the real line. */}
              {card.kind === 'personal' ? null : <Body card={card} />}
              {slot}
            </>
          )}
        </div>
      </article>
      {/* Outside the sheet, under it: a control about the deck rather than
          about this card. */}
      {after && <div className="mt-6 w-full text-center">{after}</div>}
    </section>
  );
}
