import { useRef } from 'react';
import { formatDateMedium } from '../utils/dates';
import { overlaps } from '../utils/dateTimeline';
import { SECTION_HEADING } from '../utils/classNames';

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
 * The merger list's date filter: quick ranges, and a histogram of the list
 * over time that can be dragged across for any other range, all on the date
 * each matter was notified.
 *
 * The bars are a pointer-only shortcut and hidden from assistive tech; the
 * quick ranges are the keyboard and screen-reader route, and the selected
 * range is always stated in words above the chart.
 *
 * @param {Object} props
 * @param {{from: string, to: string}|null} props.range - Inclusive YYYY-MM-DD bounds
 * @param {Object} props.timeline - From buildTimeline()
 * @param {Array} props.ranges - From quickRanges()
 * @param {{bars: number[], ranges: number[]}} props.counts
 * @param {(range: {from: string, to: string}|null) => void} props.onRangeChange
 */
function DateRangeFilter({ range, timeline, ranges, counts, onRangeChange }) {
  const { bars, unit } = timeline;
  const barsRef = useRef(null);
  const dragRef = useRef(null);

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

  const selected = (from, to) => Boolean(range && overlaps(from, to, range.from, range.to));
  const unitLabel = unit === 'week' ? 'Week of' : '';

  return (
    <div className="space-y-3">
      <p className={SECTION_HEADING}>Notification date</p>

      <div role="group" aria-label="Quick date ranges" className="flex flex-wrap gap-1.5">
        {ranges.map((r, i) => {
          const active = sameRange(r, range);
          return (
            <button
              key={r.key}
              type="button"
              aria-pressed={active}
              onClick={() => onRangeChange(active ? null : { from: r.from, to: r.to })}
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
            onClick={() => onRangeChange(null)}
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
      </div>
    </div>
  );
}

export default DateRangeFilter;
