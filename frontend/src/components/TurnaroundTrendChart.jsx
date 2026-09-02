import { memo } from 'react';
import { Line } from 'react-chartjs-2';
import '../utils/chartSetup';
import { CHART_PALETTE as COLORS } from '../constants/chartColors';
import { formatMonthLabel } from '../utils/dates';
import { formatMedian } from '../utils/formatMedian';

/**
 * Median time to decide, by decision month, against the open notification caseload.
 *
 * Two series on a shared x-axis of decision months: the median business days
 * notifications and waivers took to decide (left axis), and the notifications
 * still on the ACCC's books at each month end (right axis, shaded). Pairing
 * them is the point — it shows whether turnaround moves with the queue.
 *
 * Memoised because the Analysis page re-renders on toggles this chart doesn't
 * depend on (the window selector, the business/calendar-day switch). Its only
 * prop is the generated `monthly` block, so a re-render would rebuild identical
 * datasets and force Chart.js through a full update for nothing.
 */
function TurnaroundTrendChart({ monthly }) {
  const rows = monthly.labels.map((label, i) => ({
    label,
    notifications: monthly.notifications[i],
    waivers: monthly.waivers[i],
    caseload: monthly.open_caseload[i],
  }));

  const data = {
    labels: monthly.labels.map(formatMonthLabel),
    datasets: [
      {
        label: 'Open caseload',
        data: monthly.open_caseload,
        yAxisID: 'yCaseload',
        borderColor: 'rgba(107, 143, 127, 0.55)',
        backgroundColor: COLORS.tealLight,
        fill: true,
        borderWidth: 1.5,
        borderDash: [5, 3],
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.3,
        order: 3,
      },
      {
        label: 'Notifications (phase 1)',
        // Months held back for a thin sample carry a null median; `spanGaps`
        // bridges them so the line stays readable instead of fragmenting.
        data: monthly.notifications.map(m => m.median),
        yAxisID: 'yDays',
        borderColor: COLORS.primary,
        backgroundColor: COLORS.primary,
        borderWidth: 2.5,
        pointRadius: 3,
        pointHoverRadius: 6,
        tension: 0.3,
        spanGaps: true,
        order: 1,
      },
      {
        label: 'Waivers',
        data: monthly.waivers.map(m => m.median),
        yAxisID: 'yDays',
        borderColor: COLORS.accent,
        backgroundColor: COLORS.accent,
        borderWidth: 2.5,
        pointRadius: 3,
        pointHoverRadius: 6,
        tension: 0.3,
        spanGaps: true,
        order: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'bottom',
        labels: { usePointStyle: true, pointStyle: 'line', boxWidth: 24, font: { size: 11 } },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            const value = item.parsed.y;
            if (value === null || value === undefined) return null;
            if (item.dataset.yAxisID === 'yCaseload') return `Open caseload: ${value}`;
            const row = rows[item.dataIndex];
            const entry = item.dataset.label === 'Waivers' ? row.waivers : row.notifications;
            return `${item.dataset.label}: ${formatMedian(value)} BD (${entry.count} decided)`;
          },
        },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 11 } } },
      yDays: {
        position: 'left',
        beginAtZero: true,
        ticks: { precision: 0, font: { size: 11 } },
        grid: { color: 'rgba(0,0,0,0.04)' },
        title: {
          display: true,
          text: 'Median business days to decide',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
      },
      yCaseload: {
        position: 'right',
        beginAtZero: true,
        ticks: { precision: 0, font: { size: 11 } },
        grid: { display: false },
        title: {
          display: true,
          text: 'Open notifications',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
      },
    },
  };

  return (
    <>
      <div
        className="h-80"
        role="img"
        aria-labelledby="chart-turnaround-trend-title"
        aria-describedby="chart-turnaround-summary"
      >
        <Line data={data} options={options} role="presentation" />
      </div>
      <div className="sr-only">
        <table id="chart-turnaround-summary">
          <caption>
            Median business days to decide by decision month, with the open notification
            caseload at each month end
          </caption>
          <thead>
            <tr>
              <th>Month</th>
              <th>Notifications median (business days)</th>
              <th>Notifications decided</th>
              <th>Waivers median (business days)</th>
              <th>Waivers decided</th>
              <th>Open caseload</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.label}>
                <td>{formatMonthLabel(row.label)}</td>
                <td>{row.notifications.median === null ? 'Not reported' : formatMedian(row.notifications.median)}</td>
                <td>{row.notifications.count}</td>
                <td>{row.waivers.median === null ? 'Not reported' : formatMedian(row.waivers.median)}</td>
                <td>{row.waivers.count}</td>
                <td>{row.caseload}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default memo(TurnaroundTrendChart);
