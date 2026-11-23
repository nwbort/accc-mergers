import { FaMagnifyingGlass, FaStopwatch, FaChartLine } from 'react-icons/fa6';
import StatCard from './StatCard';
import { formatMedian } from '../utils/formatMedian';
import { MERGER_STATUS } from '../constants/mergerStatus';

/**
 * The dashboard's opening row of stat cards, from stats.json. Its own
 * component so the build-time prerenderer (src/prerender/renderStatic.jsx)
 * draws the very same cards into the homepage's raw HTML that the dashboard
 * shows once it has loaded.
 */
export default function DashboardStats({ stats }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 mb-8">
      <StatCard
        title="Mergers"
        value={`${stats.by_status[MERGER_STATUS.UNDER_ASSESSMENT] || 0} under assessment`}
        subtitle={`${stats.total_mergers} notified${stats.total_waivers ? ` and ${stats.total_waivers} waiver${stats.total_waivers !== 1 ? 's' : ''}` : ''}`}
        icon={<FaMagnifyingGlass />}
        href={`/mergers?status=${MERGER_STATUS.UNDER_ASSESSMENT}`}
      />
      <StatCard
        title="Average phase 1 duration"
        value={
          stats.phase_duration.average_business_days
            ? `${Math.round(stats.phase_duration.average_business_days)} business days`
            : 'N/A'
        }
        subtitle={
          stats.phase_duration.average_days
            ? `${Math.round(stats.phase_duration.average_days)} calendar days`
            : null
        }
        icon={<FaStopwatch />}
        href="/analysis"
      />
      <StatCard
        title="Median phase 1 duration"
        value={
          stats.phase_duration.median_business_days
            ? `${formatMedian(stats.phase_duration.median_business_days)} business days`
            : 'N/A'
        }
        subtitle={
          stats.phase_duration.median_days
            ? `${formatMedian(stats.phase_duration.median_days)} calendar days`
            : null
        }
        icon={<FaChartLine />}
        href="/analysis"
      />
    </div>
  );
}
