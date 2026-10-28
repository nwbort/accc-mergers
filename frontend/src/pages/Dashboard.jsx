import { useEffect } from 'react';
import { FaMagnifyingGlass, FaStopwatch, FaChartLine } from 'react-icons/fa6';
import StatCard from '../components/StatCard';
import OutcomeSummaryCards from '../components/OutcomeSummaryCards';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import UpcomingEventsTimeline from '../components/UpcomingEventsTimeline';
import RecentDeterminationsCards from '../components/RecentDeterminationsCards';
import RecentMergersCards from '../components/RecentMergersCards';
import PromoStack from '../components/PromoStack';
import { DASHBOARD_PROMOS } from '../constants/promo';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { getCalendarDaysUntil, isDatePast } from '../utils/dates';
import { useFetchData } from '../hooks/useFetchData';
import { markItemsAsSeen } from '../utils/lastVisit';
import { formatMedian } from '../utils/formatMedian';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/'];

function Dashboard() {
  const { data: stats, loading, error } = useFetchData(API_ENDPOINTS.stats, {
    cacheKey: 'dashboard-stats',
  });
  // A failed upcoming-events fetch shouldn't block the page — we just omit the
  // section. Errors are logged by the hook.
  const { data: upcomingEventsData } = useFetchData(API_ENDPOINTS.upcomingEvents, {
    cacheKey: 'dashboard-events',
  });
  const upcomingEvents = upcomingEventsData?.events ?? null;

  // Mark items as seen after user has viewed them for 2 seconds
  // This ensures the "New" badge persists across refreshes
  useEffect(() => {
    if (!stats) return;

    const timer = setTimeout(() => {
      const itemIds = [];
      if (stats.recent_mergers) {
        itemIds.push(...stats.recent_mergers.map(m => m.merger_id));
      }
      if (stats.recent_determinations) {
        itemIds.push(...stats.recent_determinations.map(d => d.merger_id));
      }
      markItemsAsSeen(itemIds);
    }, 2000); // 2 second delay to ensure user actually viewed the content

    return () => clearTimeout(timer);
  }, [stats]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!stats) return null;

  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      <h1 className="sr-only">Australian merger tracker dashboard</h1>
      {/* Stats Grid */}
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

      <PromoStack promos={DASHBOARD_PROMOS} />

      {/* Recent Determinations */}
      {stats.recent_determinations && (
        <div className="mb-8">
          <RecentDeterminationsCards
            determinations={stats.recent_determinations}
          />
        </div>
      )}

      {/* Recently Notified Mergers */}
      {stats.recent_mergers && (
        <div className="mb-8">
          <RecentMergersCards mergers={stats.recent_mergers} />
        </div>
      )}

      {/* Upcoming Events: the next 7 days broken out day by day, plus the
          week after bundled into a single trailing "Later" entry (handled
          inside UpcomingEventsTimeline). Calendar-day counts so the cutoff
          agrees with the day counts the timeline renders for the same
          events. */}
      {upcomingEvents && (() => {
        const eventsWithin14Days = upcomingEvents.filter(event => {
          if (isDatePast(event.date)) return false;
          const daysRemaining = getCalendarDaysUntil(event.date);
          return daysRemaining !== null && daysRemaining <= 14;
        });
        return eventsWithin14Days.length > 0 ? (
          <div className="mb-8">
            <UpcomingEventsTimeline events={eventsWithin14Days} />
          </div>
        ) : null;
      })()}

      <OutcomeSummaryCards
        speed={stats.phase_duration.percentiles}
        phase1Counts={stats.by_determination}
        phase2Counts={stats.by_phase_2_determination}
        waiverCounts={stats.by_waiver_determination}
      />
    </div>
    </>
  );
}

export default Dashboard;
