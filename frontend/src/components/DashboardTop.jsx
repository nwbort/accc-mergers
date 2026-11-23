import DashboardStats from './DashboardStats';
import PromoStack from './PromoStack';
import RecentDeterminationsCards from './RecentDeterminationsCards';
import RecentMergersCards from './RecentMergersCards';
import { DASHBOARD_PROMOS } from '../constants/promo';

/**
 * The dashboard's page wrapper. No fade-in: the build prerenders the top of
 * the dashboard into the homepage's HTML (src/prerender/renderStatic.jsx), so
 * React mounts over content that is already on screen, and fading that in
 * from transparent would only blink it.
 */
export const DASHBOARD_WRAP = 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8';

/**
 * The top of the dashboard, drawn from stats.json alone: its heading, the
 * stat cards, the promos and the recent determination and notification
 * cards. Shared by Dashboard.jsx and the build-time prerender of the
 * homepage, so the two draw the same thing in the same order; the charts and
 * timelines below it are the dashboard's own.
 */
export default function DashboardTop({ stats }) {
  return (
    <>
      <h1 className="sr-only">Australian merger tracker dashboard</h1>
      <DashboardStats stats={stats} />

      <PromoStack promos={DASHBOARD_PROMOS} />

      {stats.recent_determinations && (
        <div className="mb-8">
          <RecentDeterminationsCards determinations={stats.recent_determinations} />
        </div>
      )}

      {stats.recent_mergers && (
        <div className="mb-8">
          <RecentMergersCards mergers={stats.recent_mergers} />
        </div>
      )}
    </>
  );
}
