import { Doughnut } from 'react-chartjs-2';
import '../utils/chartSetup';
import { CARD } from '../utils/classNames';
import { CHART_PALETTE, CHART_PALETTE_ORDER, DETERMINATION_COLORS } from '../constants/chartColors';
import { MERGER_STATUS, PHASE_2_OUTCOME_ORDER } from '../constants/mergerStatus';

const CHART_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  cutout: '65%',
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        padding: 16,
        usePointStyle: true,
        pointStyle: 'circle',
        font: {
          size: 12,
          family: 'Inter, sans-serif',
        },
      },
    },
    tooltip: {
      callbacks: {
        label: (item) => {
          const total = item.dataset.data.reduce((sum, val) => sum + val, 0);
          const pct = total > 0 ? Math.round((item.parsed / total) * 100) : 0;
          return ` ${item.parsed} (${pct}%)`;
        },
      },
    },
  },
};

function doughnutData(labels, counts, fallbackColor) {
  return {
    labels,
    datasets: [
      {
        data: labels.map((label) => counts[label]),
        backgroundColor: labels.map((label, i) =>
          DETERMINATION_COLORS[label] || fallbackColor(i)
        ),
        borderWidth: 0,
        borderRadius: 4,
      },
    ],
  };
}

const paletteColor = (i) => CHART_PALETTE_ORDER[i % CHART_PALETTE_ORDER.length];

/**
 * One doughnut card. With nothing to chart it renders `emptyMessage` in the
 * same frame, or nothing at all when no message is given — the dashboard hides
 * an empty card, while /current-status keeps its grid steady across the
 * window toggle.
 */
function DoughnutCard({ id, title, labels, counts, fallbackColor, caption, labelHeading, emptyMessage }) {
  if (labels.length === 0) {
    if (!emptyMessage) return null;
    return (
      <div className={`${CARD} p-6 flex flex-col`}>
        <h2 className="text-base font-semibold text-gray-900 mb-5">{title}</h2>
        <p className="text-sm text-gray-500 flex-1 flex items-center justify-center text-center">
          {emptyMessage}
        </p>
      </div>
    );
  }
  return (
    <div className={`${CARD} p-6`}>
      <h2 id={`${id}-title`} className="text-base font-semibold text-gray-900 mb-5">
        {title}
      </h2>
      <div className="h-64" role="img" aria-labelledby={`${id}-title`} aria-describedby={`${id}-summary`}>
        <Doughnut data={doughnutData(labels, counts, fallbackColor)} options={CHART_OPTIONS} role="presentation" />
      </div>
      {/* The sr-only wrapper has to be a div: `sr-only`'s width: 1px is
          only a minimum for a table box, so a bare sr-only table lays
          out at its full content width and — being absolutely
          positioned against the viewport — widens the whole page on
          mobile. The div clips it for real. */}
      <div className="sr-only">
        <table id={`${id}-summary`}>
          <caption>{caption}</caption>
          <thead><tr><th>{labelHeading}</th><th>Count</th></tr></thead>
          <tbody>
            {labels.map((label) => (
              <tr key={label}><td>{label}</td><td>{counts[label]}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * The four summary cards that close the dashboard — phase 1 speed and the
 * phase 1, phase 2 and waiver determination breakdowns — shared with
 * /current-status, which feeds them one window's cut of the same figures.
 *
 * `speed` is the `{day15, day20, day30}` block (stats.json's
 * `phase_duration.percentiles`, or a current_status window's
 * `phase_1_speed`); the three count maps are `{outcome: count}`.
 * `idPrefix` keeps the chart ids unique on the page; `emptyMessages`
 * (`{speed, phase1, phase2, waivers}`) shows a card with nothing to chart
 * instead of hiding it.
 */
function OutcomeSummaryCards({
  speed,
  phase1Counts,
  phase2Counts,
  waiverCounts,
  idPrefix = 'chart',
  emptyMessages = {},
  className = 'grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-6',
}) {
  const phase1 = phase1Counts || {};
  const phase1Labels = Object.keys(phase1);

  // Any outcome the fixed order doesn't know about is appended rather than
  // dropped.
  const phase2 = phase2Counts || {};
  const phase2Labels = [
    ...PHASE_2_OUTCOME_ORDER.filter((label) => phase2[label]),
    ...Object.keys(phase2).filter((label) => !PHASE_2_OUTCOME_ORDER.includes(label)),
  ];

  const waivers = waiverCounts || {};
  const waiverLabels = [MERGER_STATUS.APPROVED, MERGER_STATUS.NOT_APPROVED].filter(
    (label) => waivers[label]
  );

  return (
    <div className={className}>
      {speed ? (
        <div className={`${CARD} p-6 flex flex-col`}>
          <h2 className="text-base font-semibold text-gray-900 mb-5">
            Phase 1 speed
          </h2>
          <div className="grid grid-cols-[auto_1fr_auto] items-center gap-x-4 flex-1 content-around">
            {[
              { label: 'By day 15', data: speed.day15 },
              { label: 'By day 20', data: speed.day20 },
              { label: 'By day 30', data: speed.day30 },
            ].flatMap(({ label, data }, index) => [
              <span key={`${label}-label`} className={`text-sm text-gray-600 py-3 ${index < 2 ? 'border-b border-gray-50' : ''}`}>{label}</span>,
              <div key={`${label}-bar`} className="bg-gray-100 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-primary h-1.5 rounded-full transition-all duration-500"
                  style={{ width: `${data.percentage}%` }}
                />
              </div>,
              <span key={`${label}-pct`} className={`text-sm font-semibold text-gray-900 tabular-nums text-right py-3 whitespace-nowrap ${index < 2 ? 'border-b border-gray-50' : ''}`}>
                {data.percentage}%
                <span className="text-gray-500 font-normal ml-1">({data.count})</span>
              </span>,
            ])}
          </div>
        </div>
      ) : emptyMessages.speed ? (
        <div className={`${CARD} p-6 flex flex-col`}>
          <h2 className="text-base font-semibold text-gray-900 mb-5">Phase 1 speed</h2>
          <p className="text-sm text-gray-500 flex-1 flex items-center justify-center text-center">
            {emptyMessages.speed}
          </p>
        </div>
      ) : null}

      <DoughnutCard
        id={`${idPrefix}-phase1`}
        title="Phase 1 determinations"
        labels={phase1Labels}
        counts={phase1}
        fallbackColor={paletteColor}
        caption="Phase 1 determination breakdown"
        labelHeading="Determination"
        emptyMessage={emptyMessages.phase1}
      />

      <DoughnutCard
        id={`${idPrefix}-phase2`}
        title="Phase 2 determinations"
        labels={phase2Labels}
        counts={phase2}
        fallbackColor={paletteColor}
        caption="Phase 2 determination breakdown, including ceased assessments"
        labelHeading="Outcome"
        emptyMessage={emptyMessages.phase2}
      />

      <DoughnutCard
        id={`${idPrefix}-waiver`}
        title="Waiver determinations"
        labels={waiverLabels}
        counts={waivers}
        fallbackColor={() => CHART_PALETTE.accent}
        caption="Waiver determination breakdown"
        labelHeading="Determination"
        emptyMessage={emptyMessages.waivers}
      />
    </div>
  );
}

export default OutcomeSummaryCards;
