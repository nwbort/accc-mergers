import { Bar } from 'react-chartjs-2';
import '../utils/chartSetup';
import { CHART_PALETTE as COLORS, DETERMINATION_COLORS } from '../constants/chartColors';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { CARD } from '../utils/classNames';

const SERIES = [
  { key: 'approved', label: 'Approved', color: DETERMINATION_COLORS[MERGER_STATUS.APPROVED] },
  { key: 'conditional', label: 'Approved with conditions', color: DETERMINATION_COLORS[MERGER_STATUS.APPROVED_WITH_CONDITIONS] },
  { key: 'notApproved', label: 'Not approved', color: DETERMINATION_COLORS[MERGER_STATUS.NOT_APPROVED] },
  { key: 'referred', label: 'Referred to Phase 2', color: DETERMINATION_COLORS[MERGER_STATUS.REFERRED_TO_PHASE_2] },
  { key: 'other', label: 'Other', color: COLORS.sage },
];

/**
 * One row per decision-maker (a delegated commissioner, or a division of the
 * Commission constituted under s19), stacked by outcome. `rows` is a
 * by_commission_division block from analysis.json. Matters still under
 * assessment have no decision-maker yet, so they are left off. Used for both
 * the notification and the waiver chart, which differ only in their data and
 * the label on the median.
 */
function DecisionMakerChart({ id, title, description, rows: sourceRows, medianLabel }) {
  const rows = (sourceRows ?? [])
    .filter(d => d.division !== 'Not yet determined')
    .map(d => {
      const mix = d.outcome_mix ?? {};
      const approved = mix[MERGER_STATUS.APPROVED] ?? 0;
      const conditional = mix[MERGER_STATUS.APPROVED_WITH_CONDITIONS] ?? 0;
      const notApproved = mix[MERGER_STATUS.NOT_APPROVED] ?? 0;
      const referred = mix[MERGER_STATUS.REFERRED_TO_PHASE_2] ?? 0;
      return {
        ...d,
        label: d.division === 'Unknown' ? 'Not identified' : d.division,
        approved,
        conditional,
        notApproved,
        referred,
        other: d.count - approved - conditional - notApproved - referred,
      };
    });

  if (rows.length === 0) return null;

  const series = SERIES.filter(s => rows.some(row => row[s.key] > 0));

  const data = {
    labels: rows.map(row => row.label),
    datasets: series.map(s => ({
      label: s.label,
      data: rows.map(row => row[s.key]),
      backgroundColor: s.color,
      borderRadius: 2,
      maxBarThickness: 26,
    })),
  };

  const options = {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          usePointStyle: true,
          pointStyle: 'rectRounded',
          padding: 16,
          font: { size: 12, family: 'Inter, sans-serif' },
        },
      },
      tooltip: {
        callbacks: {
          afterBody: (items) => {
            const row = rows[items[0].dataIndex];
            const median = row.median_business_days;
            return [
              `${row.count} matter${row.count === 1 ? '' : 's'} decided`,
              median == null ? '' : `${medianLabel}: ${median} business days`,
            ].filter(Boolean);
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        beginAtZero: true,
        title: {
          display: true,
          text: 'Matters decided',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 } },
      },
      y: {
        stacked: true,
        grid: { display: false },
        ticks: { font: { size: 11 } },
      },
    },
  };

  return (
    <section className="mb-8">
      <div className={`${CARD} overflow-hidden`}>
        <div className="px-6 py-5 border-b border-gray-100">
          <h2 id={`${id}-title`} className="text-base font-semibold text-gray-900">{title}</h2>
          <p className="text-sm text-gray-500 mt-0.5">{description}</p>
        </div>
        <div className="p-6">
          <div
            style={{ height: `${Math.max(240, rows.length * 48 + 90)}px` }}
            role="img"
            aria-labelledby={`${id}-title`}
            aria-describedby={`${id}-summary`}
          >
            <Bar data={data} options={options} role="presentation" />
          </div>
          <div className="sr-only">
            <table id={`${id}-summary`}>
              <caption>{title}: determinations by decision-maker and outcome</caption>
              <thead>
                <tr>
                  <th>Decision-maker</th>
                  <th>Matters</th>
                  {series.map(s => <th key={s.key}>{s.label}</th>)}
                  <th>{medianLabel} (business days)</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td>{row.count}</td>
                    {series.map(s => <td key={s.key}>{row[s.key]}</td>)}
                    <td>{row.median_business_days ?? 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

export default DecisionMakerChart;
