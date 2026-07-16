/**
 * Determination outcome -> dot colour, shared by every timeline-style view
 * that marks an event or endpoint by outcome: the header timeline bar
 * (components/MergerTimeline.jsx), the Timeline & Events list
 * (pages/MergerDetail.jsx), and the site-wide Timeline feed (pages/Timeline.jsx).
 *
 * `dot` is the plain marker fill; `ring` is the tinted halo used behind dots
 * in the Timeline & Events list. Full class strings are required so
 * Tailwind's scanner keeps them at build time.
 */

import { MERGER_STATUS } from './mergerStatus';

export const OUTCOME_DOT_COLORS = {
  [MERGER_STATUS.APPROVED]: { dot: 'bg-emerald-500', ring: 'bg-emerald-500/10' },
  [MERGER_STATUS.NOT_OPPOSED]: { dot: 'bg-emerald-500', ring: 'bg-emerald-500/10' },
  [MERGER_STATUS.DECLINED]: { dot: 'bg-red-500', ring: 'bg-red-500/10' },
  [MERGER_STATUS.NOT_APPROVED]: { dot: 'bg-red-500', ring: 'bg-red-500/10' },
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: { dot: 'bg-amber-500', ring: 'bg-amber-500/10' },
  [MERGER_STATUS.ASSESSMENT_CEASED]: { dot: 'bg-purple-500', ring: 'bg-purple-500/10' },
};

export const DEFAULT_OUTCOME_DOT = { dot: 'bg-primary', ring: 'bg-primary/10' };

// Marker for tribunal appeal events in the Timeline & Events list — indigo, to
// match the "Under appeal" badge (components/AppealBadge.jsx).
export const APPEAL_DOT = { dot: 'bg-indigo-500', ring: 'bg-indigo-500/10' };

// Determination takes precedence over status, mirroring getCardStyle.
export function getOutcomeDot({ determination, status } = {}) {
  return OUTCOME_DOT_COLORS[determination] || OUTCOME_DOT_COLORS[status] || DEFAULT_OUTCOME_DOT;
}
