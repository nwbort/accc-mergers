import { Scatter } from 'react-chartjs-2';
import '../utils/chartSetup';
import { CHART_PALETTE as COLORS } from '../constants/chartColors';

/**
 * "Share of matters concluded by day N" — one empirical CDF curve.
 *
 * Shared by /analysis, which draws it over every matter ever decided, and
 * /current-status, which draws the same curve over just the last 30 or 90
 * days of decisions. Keeping one component is what makes those two readings
 * comparable: a reader flicking between the pages is looking at the same
 * stepped curve, the same dashed median, the same statutory line, and can
 * take the difference between them as a real difference in the data.
 *
 * `points` come from `utils/durationEcdf` (either entry point — the all-time
 * nested histogram or a window's flat count map both reduce to the same
 * shape). The caller renders the card and its `<h2>`, and passes that
 * heading's id as `titleId`: the canvas is presentational, and the labelled
 * wrapper plus the `sr-only` table below it carry the whole chart for a
 * screen reader (docs/accessibility.md).
 *
 * `deadline` draws the statutory clock as a dashed vertical. Pass null where
 * it doesn't apply — on /analysis's calendar-day view the business-day
 * deadline would land in the wrong place on the axis.
 */
function DurationEcdfChart({
  points,
  median,
  deadline,
  dayLabel,
  seriesLabel,
  color,
  titleId,
  summaryId,
  caption,
  countHeading,
  minAxisMax = 0,
}) {
  // "by BD 12" reads as a business day and "by day 12" as a calendar one, so
  // the tooltip and the table header follow whichever axis is being drawn.
  const calendarDays = dayLabel === 'calendar days';
  const dayNoun = calendarDays ? 'calendar day' : 'business day';
  const shortUnit = calendarDays ? 'day' : 'BD';
  const maxX = Math.max(points[points.length - 1].x, minAxisMax) + 2;

  const data = {
    datasets: [
      ...(deadline != null ? [{
        label: `BD ${deadline} deadline`,
        data: [{ x: deadline, y: 0 }, { x: deadline, y: 100 }],
        borderColor: COLORS.accent,
        borderDash: [6, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        showLine: true,
      }] : []),
      ...(median != null ? [{
        label: `Median (${median} ${dayLabel})`,
        data: [{ x: median, y: 0 }, { x: median, y: 100 }],
        borderColor: '#9ca3af',
        borderDash: [4, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        showLine: true,
      }] : []),
      {
        label: seriesLabel,
        data: points,
        borderColor: color,
        backgroundColor: color,
        stepped: 'before',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        showLine: true,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          usePointStyle: true,
          padding: 16,
          font: { size: 12, family: 'Inter, sans-serif' },
        },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            // The two reference lines carry their whole meaning in the label;
            // only the curve has a reading at this x.
            if (item.dataset.label !== seriesLabel) return item.dataset.label;
            const { x, y, n, total } = item.raw;
            return `by ${shortUnit} ${x}: ${y}% (${n} of ${total})`;
          },
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        min: 0,
        max: maxX,
        title: {
          display: true,
          text: calendarDays ? 'Calendar days' : 'Business days',
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 } },
      },
      y: {
        min: 0,
        max: 100,
        title: {
          display: true,
          text: seriesLabel,
          font: { size: 12, family: 'Inter, sans-serif' },
          color: '#6b7280',
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
        ticks: { font: { size: 11 }, callback: (value) => `${value}%` },
      },
    },
  };

  return (
    <>
      <div
        className="h-80"
        role="img"
        aria-labelledby={titleId}
        aria-describedby={summaryId}
      >
        <Scatter data={data} options={options} role="presentation" />
      </div>
      <div className="sr-only">
        <table id={summaryId}>
          <caption>{caption}</caption>
          <thead>
            <tr>
              <th>By {dayNoun}</th>
              <th>% concluded</th>
              <th>{countHeading}</th>
            </tr>
          </thead>
          <tbody>
            {points.filter(p => p.x > 0).map(p => (
              <tr key={p.x}>
                <td>{p.x}</td>
                <td>{p.y}%</td>
                <td>{p.n} of {p.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default DurationEcdfChart;
