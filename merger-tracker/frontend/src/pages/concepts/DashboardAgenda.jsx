import { Link } from 'react-router-dom';
import { parseISO, isValid, format, startOfDay, addDays, isSameDay, differenceInCalendarDays } from 'date-fns';
import { FaRegCalendarCheck, FaArrowRightLong, FaCircleDot } from 'react-icons/fa6';
import { mergerPath } from '../../utils/slug';
import { isDatePast } from '../../utils/dates';
import { useFetchData } from '../../hooks/useFetchData';
import { API_ENDPOINTS } from '../../config';
import LoadingSpinner from '../../components/LoadingSpinner';
import SEO from '../../components/SEO';
import ConceptSwitcher from './ConceptSwitcher';

// ── Concept 6 · "Agenda" ─────────────────────────────────────────────────────
// A calendar-first dashboard built around deadlines. The register is full of
// dated obligations — consultation responses due, statutory clocks ticking — so
// this view answers "what do I need to watch, and when?" with a week strip and
// a grouped agenda. For the practitioner managing live matters against a clock.

const TYPE_DOT = {
  consultation_due: 'text-blue-500',
  notice_of_competition_concerns: 'text-amber-500',
};
const dotColour = (type) => TYPE_DOT[type] ?? 'text-purple-500';

function DashboardAgenda() {
  const { data: stats, loading, error } = useFetchData(API_ENDPOINTS.stats, { cacheKey: 'dashboard-stats' });
  const { data: upcomingData } = useFetchData(API_ENDPOINTS.upcomingEvents, { cacheKey: 'dashboard-events' });

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!stats) return null;

  const today = startOfDay(new Date());
  const events = (upcomingData?.events ?? [])
    .filter((e) => e.date && isValid(parseISO(e.date)) && !isDatePast(e.date))
    .sort((a, b) => parseISO(a.date) - parseISO(b.date));

  // 14-day strip with a per-day event count.
  const strip = Array.from({ length: 14 }, (_, i) => {
    const day = addDays(today, i);
    const count = events.filter((e) => isSameDay(parseISO(e.date), day)).length;
    return { day, count };
  });
  const maxStrip = Math.max(...strip.map((d) => d.count), 1);

  // Group all upcoming events by calendar day for the agenda list.
  const groups = [];
  events.forEach((e) => {
    const day = startOfDay(parseISO(e.date));
    const key = format(day, 'yyyy-MM-dd');
    let g = groups.find((x) => x.key === key);
    if (!g) { g = { key, day, items: [] }; groups.push(g); }
    g.items.push(e);
  });

  const within7 = events.filter((e) => differenceInCalendarDays(parseISO(e.date), today) <= 7).length;

  return (
    <>
      <SEO title="Dashboard concept · Agenda" description="Calendar/deadline ACCC merger dashboard concept." url="/concepts/agenda" />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <ConceptSwitcher current="agenda" />

        <header className="mt-8 mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-accent-dark mb-1 flex items-center gap-2">
              <FaRegCalendarCheck className="h-3.5 w-3.5" /> Deadlines diary
            </p>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
              {within7 > 0
                ? `${within7} ${within7 === 1 ? 'deadline' : 'deadlines'} in the next 7 days`
                : 'No deadlines in the next 7 days'}
            </h1>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold tabular-nums text-gray-900">{stats.by_status?.['Under assessment'] ?? 0}</div>
            <div className="text-xs text-gray-400">matters live</div>
          </div>
        </header>

        {/* Two-week strip */}
        <div className="rounded-2xl border border-gray-100 bg-white shadow-card p-4 mb-8 overflow-x-auto">
          <div className="grid grid-cols-7 gap-2 min-w-[640px]">
            {strip.map(({ day, count }) => {
              const isToday = isSameDay(day, today);
              return (
                <div key={day.toISOString()} className={`rounded-xl p-2.5 text-center ${isToday ? 'bg-primary text-white' : 'bg-gray-50'}`}>
                  <div className={`text-[10px] uppercase tracking-wide ${isToday ? 'text-white/70' : 'text-gray-400'}`}>{format(day, 'EEE')}</div>
                  <div className={`text-lg font-bold tabular-nums ${isToday ? 'text-white' : 'text-gray-900'}`}>{format(day, 'd')}</div>
                  <div className="mt-1.5 h-8 flex items-end justify-center">
                    {count > 0 ? (
                      <div
                        className={`w-2 rounded-full ${isToday ? 'bg-white' : 'bg-accent'}`}
                        style={{ height: `${(count / maxStrip) * 100}%`, minHeight: '0.5rem' }}
                        title={`${count} event${count === 1 ? '' : 's'}`}
                      />
                    ) : (
                      <div className={`text-[10px] ${isToday ? 'text-white/50' : 'text-gray-300'}`}>—</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Agenda grouped by day */}
        {groups.length === 0 ? (
          <div className="rounded-2xl border border-gray-100 bg-white shadow-card p-10 text-center text-gray-400">
            Nothing scheduled on the register right now.
          </div>
        ) : (
          <div className="space-y-6">
            {groups.map(({ key, day, items }) => {
              const days = differenceInCalendarDays(day, today);
              return (
                <div key={key} className="flex gap-4 sm:gap-6">
                  {/* Date rail */}
                  <div className="w-16 sm:w-20 shrink-0 text-right">
                    <div className="text-xs uppercase tracking-wide text-gray-400">{format(day, 'EEE')}</div>
                    <div className="text-2xl font-bold tabular-nums text-gray-900 leading-tight">{format(day, 'd')}</div>
                    <div className="text-xs text-gray-400">{format(day, 'MMM')}</div>
                    <div className={`mt-1 text-[11px] font-medium ${days <= 3 ? 'text-red-600' : 'text-primary'}`}>
                      {days === 0 ? 'today' : days === 1 ? 'tomorrow' : `in ${days} days`}
                    </div>
                  </div>
                  {/* Items */}
                  <div className="flex-1 space-y-2 border-l border-gray-100 pl-4 sm:pl-6">
                    {items.map((e) => (
                      <Link
                        key={`${e.merger_id}-${e.type}`}
                        to={mergerPath(e.merger_id, e.merger_name)}
                        className="block rounded-xl border border-gray-100 bg-white shadow-card hover:shadow-card-hover hover:border-gray-200 transition-all px-4 py-3 group"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <FaCircleDot className={`h-2.5 w-2.5 ${dotColour(e.type)}`} />
                          <span className="text-xs font-semibold text-gray-500">{e.event_type_display}</span>
                        </div>
                        <p className="text-sm font-medium text-gray-900 group-hover:text-primary transition-colors leading-snug">{e.merger_name}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{e.merger_id} · {e.stage}</p>
                      </Link>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

export default DashboardAgenda;
