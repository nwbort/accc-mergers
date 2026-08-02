import { Link } from 'react-router';
import {
  FaHourglassHalf,
  FaBell,
  FaCalendarPlus,
  FaArrowTrendUp,
} from 'react-icons/fa6';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import StatusBadge from '../components/StatusBadge';
import StatCard from '../components/StatCard';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { mergerPath } from '../utils/slug';
import { formatDateMedium } from '../utils/dates';
import { THEME_HEXES } from '../constants/chartColors';
import { CARD } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/extensions'];

// Reason categories map to a fixed colour so the clock bars, the legend and the
// "why the clock was extended" breakdown all read as one palette.
const REASON_STYLE = {
  'Requested by the merger parties': { color: THEME_HEXES.primary, label: 'Requested by the merger parties' },
  'ACCC information request': { color: THEME_HEXES.phase2, label: 'ACCC information request' },
  'Remedy under consideration': { color: THEME_HEXES.phase2Referral, label: 'Remedy under consideration' },
  Other: { color: '#94a3b8', label: 'Other' },
};

const BASE_CLOCK_COLOR = '#E5E7EB'; // gray-200 — the statutory 30-BD window

function ReasonBreakdown({ reasons }) {
  const maxEvents = Math.max(...reasons.map((r) => r.events), 1);
  return (
    <div className={`${CARD} p-5 sm:p-6`}>
      <ul className="space-y-4">
        {reasons.map((r) => {
          const style = REASON_STYLE[r.category] || REASON_STYLE.Other;
          return (
            <li key={r.category}>
              <div className="flex items-center justify-between gap-3 mb-1.5">
                <span className="flex items-center gap-2 text-sm font-medium text-gray-800">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: style.color }} />
                  {r.category}
                </span>
                <span className="text-xs text-gray-500 whitespace-nowrap">
                  {r.events} notice{r.events !== 1 ? 's' : ''} · +{r.business_days} BD
                </span>
              </div>
              <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${(r.events / maxEvents) * 100}%`, backgroundColor: style.color }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// A single matter's Phase 1 clock: the statutory 30-BD base plus one segment per
// extension, widths scaled against the longest clock on the page so the bars are
// comparable to each other.
function ClockBar({ matter, statutoryBd, scaleMax }) {
  const segments = [{ bd: statutoryBd, color: BASE_CLOCK_COLOR, label: `${statutoryBd} BD statutory clock` }];
  matter.extensions.forEach((ext) => {
    const style = REASON_STYLE[ext.reason_category] || REASON_STYLE.Other;
    segments.push({
      bd: ext.business_days,
      color: style.color,
      unknown: ext.business_days === null,
      label: ext.business_days !== null
        ? `+${ext.business_days} BD — ${ext.reason_category}`
        : `Extended (length not published) — ${ext.reason_category}`,
    });
  });

  const totalBd = statutoryBd + (matter.total_extension_bd || 0);
  // Unknown-length extensions get a nominal slice so they stay visible.
  const widthFor = (seg) => `${((seg.unknown ? 4 : seg.bd) / scaleMax) * 100}%`;

  return (
    <div
      className="flex h-6 w-full rounded-lg overflow-hidden bg-gray-50"
      role="img"
      aria-label={`${matter.merger_name}: 30-business-day statutory clock extended to ${matter.total_extension_bd ? `${totalBd} business days` : 'an unpublished length'} across ${matter.extension_count} notice${matter.extension_count !== 1 ? 's' : ''}`}
    >
      {segments.map((seg, i) => (
        <div
          key={i}
          className={`h-full ${seg.unknown ? 'bg-[repeating-linear-gradient(45deg,transparent,transparent_3px,rgba(255,255,255,0.5)_3px,rgba(255,255,255,0.5)_6px)]' : ''}`}
          style={{ width: widthFor(seg), backgroundColor: seg.color }}
          title={seg.label}
        />
      ))}
    </div>
  );
}

function MatterCard({ matter, scaleMax, statutoryBd }) {
  const totalBd = statutoryBd + (matter.total_extension_bd || 0);
  return (
    <li className="py-5 first:pt-0 last:pb-0">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <Link
            to={mergerPath(matter.merger_id, matter.merger_name)}
            className="block text-sm font-semibold text-gray-900 hover:text-primary transition-colors truncate"
          >
            {matter.merger_name}
          </Link>
          <p className="text-xs text-gray-500 mt-0.5">{matter.merger_id}</p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          {matter.escalated_to_phase_2 && (
            <Link
              to="/phase-2"
              className="inline-flex items-center rounded-full border border-phase-2/30 bg-phase-2-pale px-2.5 py-0.5 text-xs font-medium text-phase-2-dark hover:bg-phase-2/10 transition-colors"
            >
              → Phase 2
            </Link>
          )}
          <StatusBadge status={matter.status} />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <ClockBar matter={matter} statutoryBd={statutoryBd} scaleMax={scaleMax} />
        </div>
        <div className="flex-shrink-0 text-right">
          <span className="text-sm font-bold text-gray-900">
            {matter.total_extension_bd !== null ? `${statutoryBd} → ${totalBd}` : `${statutoryBd} → ?`}
          </span>
          <span className="block text-[11px] text-gray-500">business days</span>
        </div>
      </div>

      <ul className="mt-3 space-y-1">
        {matter.extensions.map((ext, i) => {
          const style = REASON_STYLE[ext.reason_category] || REASON_STYLE.Other;
          return (
            <li key={i} className="flex items-baseline gap-2 text-xs text-gray-600">
              <span className="h-2 w-2 flex-shrink-0 translate-y-0.5 rounded-full" style={{ backgroundColor: style.color }} />
              <span className="font-medium text-gray-800 whitespace-nowrap">
                {ext.business_days !== null ? `+${ext.business_days} BD` : 'Extended'}
              </span>
              <span className="text-gray-400">·</span>
              <span className="whitespace-nowrap">{formatDateMedium(ext.date)}</span>
              {ext.reason_detail && (
                <>
                  <span className="text-gray-400">·</span>
                  <span className="min-w-0 truncate">{ext.reason_detail}</span>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </li>
  );
}

function Extensions() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.extensions, { cacheKey: 'extensions' });

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;

  const summary = data?.summary || {};
  const reasons = data?.reasons || [];
  const matters = data?.matters || [];
  const statutoryBd = summary.statutory_phase_1_bd || 30;

  const scaleMax = Math.max(
    statutoryBd + 1,
    ...matters.map((m) => statutoryBd + (m.total_extension_bd || 0)),
  );

  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/extensions"
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            Phase 1 timeline extensions
          </h1>
          <p className="mt-3 max-w-3xl text-sm text-gray-600 leading-relaxed">
            The ACCC has a <strong>{statutoryBd} business day</strong> statutory clock to make its Phase 1
            determination. That clock can be stretched — usually at the merger parties&apos; request, or
            when the ACCC needs more information or is weighing a remedy. Each time, the register
            publishes a &ldquo;timeline extended&rdquo; notice. This page tracks every one.
          </p>
        </header>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            title="Matters extended"
            value={summary.matters_extended}
            subtitle={`${summary.share_extended_pct}% of ${summary.notifications_total} notifications`}
            icon={<FaHourglassHalf />}
          />
          <StatCard
            title="Extension notices"
            value={summary.extension_events_total}
            subtitle={`${summary.total_extension_bd} business days added in total`}
            icon={<FaBell />}
          />
          <StatCard
            title="Median extension"
            value={summary.median_matter_extension_bd != null ? `${summary.median_matter_extension_bd} BD` : 'N/A'}
            subtitle={summary.longest_single_bd != null ? `Longest single: ${summary.longest_single_bd} BD` : undefined}
            icon={<FaCalendarPlus />}
          />
          <StatCard
            title="Later went to Phase 2"
            value={summary.extended_escalated_to_phase_2}
            subtitle={`${summary.escalation_rate_given_extension_pct}% of extended matters`}
            icon={<FaArrowTrendUp />}
            href="/phase-2"
          />
        </div>

        {summary.phase_2_preceded_by_extension_pct != null && (
          <div className="mb-8 rounded-2xl border border-phase-2-referral/30 bg-phase-2-referral-pale/60 p-5 sm:p-6">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-phase-2-referral-dark">
              <FaArrowTrendUp aria-hidden="true" />
              An extension is an early warning sign
            </h2>
            <p className="mt-2 text-sm text-gray-700 leading-relaxed">
              A Phase 1 extension is one of the strongest public signals that a deal is in trouble.
              Just <strong>{summary.base_phase_2_rate_pct}%</strong> of all notifications reach Phase 2 — but{' '}
              <strong>{summary.escalation_rate_given_extension_pct}%</strong> of matters that were extended
              did. Looked at the other way, <strong>{summary.phase_2_preceded_by_extension_pct}%</strong> of
              every Phase 2 escalation so far ({summary.extended_escalated_to_phase_2} of{' '}
              {summary.phase_2_total}) had its Phase 1 clock extended first.
            </p>
          </div>
        )}

        <section aria-labelledby="reasons-heading" className="mb-8">
          <h2 id="reasons-heading" className="text-lg font-semibold text-gray-900 mb-4">
            Why the clock was extended
          </h2>
          <ReasonBreakdown reasons={reasons} />
        </section>

        <section aria-labelledby="matters-heading">
          <h2 id="matters-heading" className="text-lg font-semibold text-gray-900 mb-1">
            Extended matters
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Each bar shows the {statutoryBd}-business-day statutory clock (grey) plus every extension,
            coloured by reason. Longest clock first.
          </p>
          {matters.length === 0 ? (
            <div className={`${CARD} p-6`}>
              <p className="text-gray-500 text-sm">No Phase 1 extensions have been published yet.</p>
            </div>
          ) : (
            <div className={`${CARD} p-5 sm:p-6`}>
              <ul className="divide-y divide-gray-100">
                {matters.map((matter) => (
                  <MatterCard
                    key={matter.merger_id}
                    matter={matter}
                    scaleMax={scaleMax}
                    statutoryBd={statutoryBd}
                  />
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

export default Extensions;
