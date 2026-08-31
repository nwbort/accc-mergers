import LoadingSpinner from '../components/LoadingSpinner';
import ErrorCard from '../components/ErrorCard';
import IndustryMergerGroups from '../components/IndustryMergerGroups';
import PhaseDurationComparison from '../components/PhaseDurationComparison';
import SEO from '../components/SEO';
import Breadcrumb from '../components/Breadcrumb';
import DetailStatGrid from '../components/DetailStatGrid';
import PartyMembers from '../components/PartyMembers';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { useDecodedParam } from '../hooks/useDecodedParam';
import { partyMeta } from '../utils/pageMeta';
import { CARD, SECTION_HEADING } from '../utils/classNames';

const ROLE_LABELS = {
  acquirer: 'As acquirer',
  target: 'As target',
  other: 'As other party',
};

function PartyDetail() {
  const decodedId = useDecodedParam('id');

  // Party records are packed into fixed shard buckets, so this fetches the
  // bucket the id hashes into and picks the record out of it. The bucket is
  // computed from the id alone (no index lookup), so a party page is still one
  // request. Caching on the bucket rather than the party is a small bonus:
  // browsing several parties often reuses an already-fetched bucket.
  const shardUrl = decodedId ? API_ENDPOINTS.partyShard(decodedId) : null;
  const { data: shard, loading, error } = useFetchData(
    shardUrl,
    { cacheKey: `party-shard-${shardUrl}` }
  );

  const data = shard?.parties?.[decodedId] ?? null;

  // Overall all-mergers figures, for comparing this party's Phase 1 duration
  // against the market as a whole. Non-fatal if it fails to load.
  const { data: statsData } = useFetchData(
    data ? API_ENDPOINTS.stats : null,
    data ? { cacheKey: 'dashboard-stats' } : {}
  );

  // Two ways a party can be missing now: its bucket doesn't exist (nothing has
  // ever hashed there), or the bucket loaded fine but holds no such id. Both
  // mean the same thing to the reader, so they get the same card.
  const isNotFound = error === 'HTTP 404' || (!loading && !error && !!shard && !data);

  if (loading) return <LoadingSpinner />;

  if (error || isNotFound) {
    return (
      <ErrorCard
        title={isNotFound ? 'Party not found' : 'Error loading party'}
        message={isNotFound
          ? `We couldn't find a party with id "${decodedId}".`
          : error
        }
        backTo="/parties"
        backLabel="Back to parties"
      />
    );
  }

  if (!data) return null;

  // Built by the same helper the build-time prerenderer uses, so the raw HTML
  // crawlers read and the head React renders here cannot drift apart.
  const meta = partyMeta(data, decodedId);
  const partyName = meta.name;
  const mergerCount = meta.mergerCount;
  const members = data.members || [];
  const mergersByRole = data.mergers || {};

  const statCards = [
    { label: 'Total reviews', value: mergerCount },
    { label: 'Phase 2 reviews', value: data.phase_2_count ?? 0 },
    { label: 'Waivers', value: data.waiver_count ?? 0 },
    { label: 'Under assessment', value: data.active_count ?? 0 },
  ];

  const duration = data.phase_duration;
  const comparisons = [];
  if (statsData?.phase_duration) {
    comparisons.push({ name: 'All mergers', duration: statsData.phase_duration });
  }

  const waiverDuration = data.waiver_duration;
  const waiverComparisons = [];
  if (statsData?.waiver_duration?.average_business_days != null) {
    waiverComparisons.push({ name: 'All mergers', duration: statsData.waiver_duration });
  }

  const roles = ['acquirer', 'target', 'other'].filter((role) => (mergersByRole[role] || []).length > 0);

  return (
    <>
      <SEO
        title={meta.title}
        description={meta.description}
        url={meta.path}
        structuredData={meta.structuredData}
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <Breadcrumb
          ariaLabel="Party breadcrumb"
          items={[
            { label: 'Parties', to: '/parties' },
            { label: partyName },
          ]}
        />

        <div className={`${CARD} p-6 mb-6 card-accent`}>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{partyName}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {mergerCount} merger{mergerCount !== 1 ? 's' : ''}
          </p>

          <PartyMembers members={members} partyName={partyName} />
        </div>

        {mergerCount > 0 && <DetailStatGrid statCards={statCards} />}

        {mergerCount > 0 && duration?.average_business_days != null && (
          <div className="mb-6">
            <PhaseDurationComparison
              duration={duration}
              comparisons={comparisons}
              subjectLabel="This party"
            />
          </div>
        )}

        {mergerCount > 0 && waiverDuration?.average_business_days != null && (
          <div className="mb-6">
            <PhaseDurationComparison
              title="Waiver duration"
              duration={waiverDuration}
              comparisons={waiverComparisons}
              subjectLabel="This party"
            />
          </div>
        )}

        {roles.map((role) => (
          <div key={role} className="mb-8">
            <h2 className={`${SECTION_HEADING} mb-3`}>
              {ROLE_LABELS[role]}
            </h2>
            <IndustryMergerGroups mergers={mergersByRole[role]} variant="full" />
          </div>
        ))}

        {mergerCount === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-500 font-medium">No mergers found for this party</p>
          </div>
        )}
      </div>
    </>
  );
}

export default PartyDetail;
