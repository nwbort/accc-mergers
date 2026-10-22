import { useRef } from 'react';
import { formatDateMedium } from '../utils/dates';
import { overlaps } from '../utils/dateTimeline';
import { DATE_FIELDS } from '../utils/mergerFilters';
import { SECTION_HEADING } from '../utils/classNames';

const FIELD_HELP = {
  notified: 'When the matter was notified, or the waiver applied for.',
  determined: 'When the ACCC published its determination.',
  open: 'Open at any point in the range: notified by its end, not yet decided by its start.',
};

const MAX_ALIGNED_MONTHS = 24;
const OPEN_START = '0000-01-01';
const OPEN_END = '9999-12-31';

function rangeLabel(range) {
  if (!range) return 'Any time';
  const { from, to } = range;
  if (from === OPEN_START) return `Up to ${formatDateMedium(to)}`;
  if (to === OPEN_END) return `From ${formatDateMedium(from)}`;
  if (from === to) return formatDateMedium(from);
  return `${formatDateMedium(from)} – ${formatDateMedium(to)}`;
}

const sameRange = (a, b) => Boolean(a && b && a.from === b.from && a.to === b.to);

/**
 * The merger list's date filter: a histogram of the list over time that can
 * be dragged across, the months under it as buttons, and quick ranges beside
 * it, on whichever date the reader picks.
 *
 * The bars are a pointer-only shortcut and hidden from assistive tech; the
 * month buttons and quick ranges reach every range the bars can, a month at a
 * time, from a keyboard or screen reader.
 *
 * @param {Object} props
 * @param {string} props.field - 'notified' | 'determined' | 'open'
 * @param {{from: string, to: string}|null} props.range - Inclusive YYYY-MM-DD bounds
 * @param {Object} props.timeline - From buildTimeline()
 * @param {Array} props.ranges - From quickRanges()
 * @param {{bars: number[], months: number[], ranges: number[]}} props.counts
 * @param {(field: string) => void} props.onFieldChange
 * @param {(range: {from: string, to: string}|null) => void} props.onRangeChange
 */
function DateRangeFilter({ field, range, timeline, ranges, counts, onFieldChange, onRangeChange }) {
  const { bars, months, unit } = timeline;
  const barsRef = useRef(null);
  const dragRef = useRef(null);
  // A tapped month waiting for a second tap to make it a range. Kept with the
  // range it set, so a drag, a quick range or a cleared filter in between
  // means the next tap starts afresh rather than extending something stale.
  const anchorRef = useRef(null);

  const maxCount = Math.max(1, ...counts.bars);
  const columns = { gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))` };

  const barAt = (clientX) => {
    const rect = barsRef.current.getBoundingClientRect();
    const i = Math.floor(((clientX - rect.left) / rect.width) * bars.length);
    return Math.max(0, Math.min(bars.length - 1, i));
  };

  const selectBars = (a, b) => {
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    const next = { from: bars[lo].from, to: bars[hi].to };
    anchorRef.current = null;
    if (!sameRange(next, range)) onRangeChange(next);
  };

  const onPointerDown = (e) => {
    if (e.button !== undefined && e.button !== 0) return;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    const i = barAt(e.clientX);
    dragRef.current = i;
    selectBars(i, i);
  };
  const onPointerMove = (e) => {
    if (dragRef.current === null) return;
    selectBars(dragRef.current, barAt(e.clientX));
  };
  const endDrag = () => { dragRef.current = null; };

  const tapMonth = (i) => {
    const anchor = anchorRef.current;
    if (anchor && sameRange(anchor.range, range) && anchor.index !== i) {
      const lo = months[Math.min(anchor.index, i)];
      const hi = months[Math.max(anchor.index, i)];
      const next = { from: lo.from, to: hi.to };
      anchorRef.current = null;
      onRangeChange(next);
      return;
    }
    const next = { from: months[i].from, to: months[i].to };
    anchorRef.current = { index: i, range: next };
    onRangeChange(next);
  };

  const selected = (from, to) => Boolean(range && overlaps(from, to, range.from, range.to));
  const monthName = (mo, i) => `${mo.name} ${mo.year}, ${counts.months[i]} mergers`;
  // Past two years the months under the bars get too narrow to press, even
  // on a wide screen; the wrapping grid takes over everywhere.
  const alignedMonths = months.length <= MAX_ALIGNED_MONTHS;
  const unitLabel = unit === 'week' ? 'Week of' : '';

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <p className={SECTION_HEADING} id="date-filter-heading">Date</p>
        <div role="group" aria-label="Date to filter on" className="flex rounded-lg border border-gray-200 bg-white p-0.5">
          {DATE_FIELDS.map((f) => (
            <button
              key={f.value}
              type="button"
              aria-pressed={field === f.value}
              onClick={() => onFieldChange(f.value)}
              className={`px-2.5 py-1 rounded-md text-sm transition-colors ${
                field === f.value ? 'bg-primary text-white' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-gray-500">{FIELD_HELP[field]}</p>

      <div role="group" aria-label="Quick date ranges" className="flex flex-wrap gap-1.5">
        {ranges.map((r, i) => {
          const active = sameRange(r, range);
          return (
            <button
              key={r.key}
              type="button"
              aria-pressed={active}
              onClick={() => { anchorRef.current = null; onRangeChange(active ? null : { from: r.from, to: r.to }); }}
              className={`px-3 py-1 rounded-full text-sm border transition-colors ${
                active
                  ? 'bg-primary text-white border-primary'
                  : 'bg-white text-gray-700 border-gray-200 hover:border-gray-300'
              }`}
            >
              {r.label}
              <span className={`ml-1.5 tabular-nums ${active ? 'text-white/80' : 'text-gray-500'}`}>{counts.ranges[i]}</span>
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between gap-3 min-h-[1.75rem]">
        <p className={`text-sm tabular-nums ${range ? 'font-semibold text-gray-900' : 'text-gray-500'}`} aria-live="polite">
          {rangeLabel(range)}
        </p>
        {range && (
          <button
            type="button"
            onClick={() => { anchorRef.current = null; onRangeChange(null); }}
            className="text-xs text-gray-500 hover:text-gray-700 underline p-1"
          >
            Clear dates
          </button>
        )}
      </div>

      <div>
        {/* Drag across the bars for a range, or press one for its week. */}
        <div
          ref={barsRef}
          aria-hidden="true"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          className="grid items-end gap-px h-20 cursor-crosshair select-none"
          style={{ ...columns, touchAction: 'pan-y' }}
        >
          {bars.map((b, i) => {
            const n = counts.bars[i];
            const on = selected(b.from, b.to);
            return (
              <div
                key={b.from}
                title={`${unitLabel} ${formatDateMedium(b.from)}: ${n}`.trim()}
                className={`rounded-t-sm ${
                  n === 0 ? 'border-b border-gray-200' : on ? 'bg-primary' : 'bg-primary/20'
                }`}
                style={{ height: n === 0 ? '1px' : `${Math.max(4, (n / maxCount) * 100)}%` }}
              />
            );
          })}
        </div>
        {/* Under the bars, each month spans its own weeks. Where that would
            make them narrower than a fingertip (phones, or a long register),
            they wrap as a grid of their own instead. Only one of the two is
            ever displayed, so assistive tech meets one set of buttons. */}
        {alignedMonths && (
          <div role="group" aria-labelledby="date-filter-heading" className="hidden sm:grid gap-px" style={columns}>
            {months.map((mo, i) => (
              <button
                key={mo.key}
                type="button"
                aria-pressed={selected(mo.from, mo.to)}
                aria-label={monthName(mo, i)}
                onClick={() => tapMonth(i)}
                style={{ gridColumn: `${mo.firstBar + 1} / ${mo.lastBar + 2}` }}
                className={`min-w-0 overflow-hidden pt-1 pb-0.5 text-left border-t-2 leading-tight transition-colors ${
                  selected(mo.from, mo.to)
                    ? 'border-primary text-gray-900 font-semibold'
                    : 'border-gray-200 text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {mo.showsName && <span className="block text-xs whitespace-nowrap">{mo.name}</span>}
                {mo.showsYear && <span className="block text-[10px] text-gray-500 font-normal tabular-nums">{mo.year}</span>}
              </button>
            ))}
          </div>
        )}
        <div
          role="group"
          aria-labelledby="date-filter-heading"
          className={`${alignedMonths ? 'grid sm:hidden' : 'grid'} mt-2 gap-1.5 grid-cols-[repeat(auto-fill,minmax(3.25rem,1fr))]`}
        >
          {months.map((mo, i) => (
            <button
              key={mo.key}
              type="button"
              aria-pressed={selected(mo.from, mo.to)}
              aria-label={monthName(mo, i)}
              onClick={() => tapMonth(i)}
              className={`flex flex-col items-center py-1 rounded-lg border text-xs leading-tight transition-colors ${
                selected(mo.from, mo.to)
                  ? 'border-primary bg-primary/5 text-gray-900 font-semibold'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              <span>{mo.name}</span>
              {/* gray-600, not 500: it has to clear 4.5:1 on the selected tint too. */}
              <span className="text-[10px] text-gray-600 font-normal tabular-nums">{mo.year}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-gray-500">
          Drag across the bars, or tap a month and then another to cover the months between.
        </p>
      </div>
    </div>
  );
}

export default DateRangeFilter;
