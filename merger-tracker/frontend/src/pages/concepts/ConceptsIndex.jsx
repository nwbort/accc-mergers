import { Link } from 'react-router-dom';
import { FaArrowRightLong, FaNewspaper, FaGaugeHigh, FaFeather, FaTableCellsLarge, FaLayerGroup, FaRegCalendarCheck } from 'react-icons/fa6';
import SEO from '../../components/SEO';

// Landing page for the three dashboard design concepts. This is a review
// scaffold (linked from /concepts) so the alternatives can be compared on the
// Cloudflare preview without disturbing the live dashboard at "/".

const CONCEPTS = [
  {
    to: '/concepts/pulse',
    icon: FaNewspaper,
    name: 'Pulse',
    tag: 'Newsroom',
    audience: 'The follower — journalists, associates doing a morning sweep',
    blurb:
      'A live activity stream that merges new notifications and determinations into one chronological feed, fronted by a numbers ticker and a one-sentence "week in mergers" lede. Answers "what just happened?" first.',
    preview: 'from-blue-500 via-emerald-500 to-primary',
  },
  {
    to: '/concepts/command',
    icon: FaGaugeHigh,
    name: 'Command Deck',
    tag: 'Analyst',
    audience: 'The deal-maker — competition lawyers, corp-dev benchmarking a deal',
    blurb:
      'A dark data-terminal. Big KPI tiles, a clearance-velocity gauge (% cleared by day 15/20/30), a phase pipeline funnel and an outcomes doughnut. Built to benchmark timing and likelihood at a glance.',
    preview: 'from-primary-dark via-primary to-primary-light',
  },
  {
    to: '/concepts/clarity',
    icon: FaFeather,
    name: 'Clarity',
    tag: 'Editorial',
    audience: 'The newcomer — public readers, anyone arriving cold',
    blurb:
      'A calm, single-column brief. One big sentence states the position, a few large figures follow, then quiet hairline lists of determinations, deadlines and where the deals are. Reads like the cover of a report.',
    preview: 'from-gray-100 via-white to-gray-50',
  },
  {
    to: '/concepts/bento',
    icon: FaTableCellsLarge,
    name: 'Bento',
    tag: 'Glanceable',
    audience: 'The casual visitor — anyone wanting the whole picture in one screen',
    blurb:
      'A colour-blocked bento grid of asymmetric tiles, each metric sized to its weight and tinted with the existing phase / outcome palette. Playful and dense without a scroll — the dashboard as a single composed screen.',
    preview: 'from-primary via-cleared to-phase-1',
  },
  {
    to: '/concepts/atlas',
    icon: FaLayerGroup,
    name: 'Atlas',
    tag: 'Sector-first',
    audience: 'The economist / policy watcher — where is review concentrating?',
    blurb:
      'Leads with place, not time: a treemap-style heatmap of industries packed by deal volume and shaded by intensity. Click a sector to drill in. Surfaces which corners of the economy the ACCC is busiest in.',
    preview: 'from-primary-dark via-primary to-primary/40',
  },
  {
    to: '/concepts/agenda',
    icon: FaRegCalendarCheck,
    name: 'Agenda',
    tag: 'Calendar',
    audience: 'The practitioner — managing live matters against a statutory clock',
    blurb:
      'A deadlines diary: a two-week strip showing where obligations fall, then a grouped agenda of every upcoming event by day. Answers "what do I need to watch, and when?" first.',
    preview: 'from-accent-dark via-accent to-emerald-300',
  },
];

function ConceptsIndex() {
  return (
    <>
      <SEO title="Dashboard design concepts" description="Three design directions for the ACCC merger tracker dashboard." url="/concepts" />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 animate-fade-in">
        <header className="mb-10 max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-widest text-accent-dark mb-2">Design exploration</p>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-gray-900">Six dashboard concepts</h1>
          <p className="mt-3 text-gray-500 leading-relaxed">
            Each takes the same live ACCC data in a different direction, aimed at a different reader.
            They live alongside the current dashboard at <Link to="/" className="text-primary hover:underline">/</Link> so nothing is replaced —
            pick the direction that fits and we can promote it.
          </p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {CONCEPTS.map((c) => {
            const Icon = c.icon;
            return (
              <Link
                key={c.to}
                to={c.to}
                className="group flex flex-col rounded-2xl border border-gray-100 bg-white shadow-card hover:shadow-card-hover hover:border-gray-200 transition-all duration-200 overflow-hidden"
              >
                <div className={`h-24 bg-gradient-to-br ${c.preview} flex items-center justify-center`}>
                  <Icon className="h-8 w-8 text-white/90 drop-shadow" />
                </div>
                <div className="p-5 flex flex-col flex-1">
                  <div className="flex items-center gap-2 mb-1.5">
                    <h2 className="text-lg font-bold text-gray-900">{c.name}</h2>
                    <span className="text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-md bg-gray-100 text-gray-500">{c.tag}</span>
                  </div>
                  <p className="text-xs font-medium text-primary mb-2">{c.audience}</p>
                  <p className="text-sm text-gray-500 leading-relaxed flex-1">{c.blurb}</p>
                  <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-primary group-hover:gap-2.5 transition-all">
                    View concept <FaArrowRightLong className="h-3 w-3" />
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </>
  );
}

export default ConceptsIndex;
