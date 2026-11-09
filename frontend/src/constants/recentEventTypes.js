import {
  FaCirclePlus,
  FaCircleExclamation,
  FaCircleCheck,
  FaRegComments,
  FaHourglassHalf,
  FaGavel,
  FaArrowRight,
  FaTriangleExclamation,
  FaHandshake,
  FaFileSignature,
  FaStamp,
  FaFileLines,
  FaHandHoldingHeart,
  FaBan,
  FaScaleBalanced,
  FaLandmark,
  FaCircleInfo,
} from 'react-icons/fa6';

// Every event type recent-events.json can carry (the Python classifier,
// scripts/generate/static_data/outputs/recent_events.py, decides which an
// event is). `shown` decides whether the dashboard's "Recent events" timeline
// lists it: the feed publishes every type, so narrowing the timeline is a
// matter of flipping a flag here, not of regenerating the data.
//
// Hidden by default: notifications, phase 1 and waiver determinations (the
// dashboard's own cards already list them) and the routine phase 1
// consultation every notification gets. Second-round consultations — phase 2,
// remedy and public benefit questionnaires — stay.
//
// Key order is significance: within a day the timeline lists the most
// consequential events first (recentEventRank). `plural` is a collapsed
// group's label ("3 timeline extensions"). Tile/chip colours follow
// UpcomingEventsTimeline's: a pale fill with the family's dark text, so each
// chip clears AA as small text. Full class strings keep Tailwind's scanner
// happy.
export const RECENT_EVENT_TYPES = {
  tribunal: {
    label: 'Tribunal',
    plural: 'Tribunal filings',
    Icon: FaScaleBalanced,
    tile: 'bg-rose-50 text-rose-600',
    chip: 'bg-rose-50 text-rose-700 border-rose-200/60',
    shown: true,
  },
  federal_court: {
    label: 'Federal Court',
    plural: 'Federal Court filings',
    Icon: FaLandmark,
    tile: 'bg-rose-50 text-rose-600',
    chip: 'bg-rose-50 text-rose-700 border-rose-200/60',
    shown: true,
  },
  phase_2_determination: {
    label: 'Phase 2 determination',
    plural: 'phase 2 determinations',
    Icon: FaGavel,
    tile: 'bg-purple-50 text-purple-600',
    chip: 'bg-purple-50 text-purple-700 border-purple-200/60',
    shown: true,
  },
  reasons: {
    label: 'Reasons',
    plural: 'reasons documents',
    Icon: FaFileLines,
    tile: 'bg-purple-50 text-purple-600',
    chip: 'bg-purple-50 text-purple-700 border-purple-200/60',
    shown: true,
  },
  undertaking_accepted: {
    label: 'Undertaking accepted',
    plural: 'undertakings accepted',
    Icon: FaFileSignature,
    tile: 'bg-emerald-50 text-emerald-700',
    chip: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
    shown: true,
  },
  ceased: {
    label: 'Ceased',
    plural: 'assessments ceased',
    Icon: FaBan,
    tile: 'bg-gray-100 text-gray-600',
    chip: 'bg-gray-50 text-gray-700 border-gray-200/60',
    shown: true,
  },
  phase_2_referral: {
    label: 'Phase 2 referral',
    plural: 'phase 2 referrals',
    Icon: FaArrowRight,
    tile: 'bg-amber-50 text-amber-700',
    chip: 'bg-amber-50 text-amber-700 border-amber-200/60',
    shown: true,
  },
  competition_concerns: {
    label: 'Concerns notice',
    plural: 'concerns notices',
    Icon: FaTriangleExclamation,
    tile: 'bg-amber-50 text-amber-700',
    chip: 'bg-amber-50 text-amber-700 border-amber-200/60',
    shown: true,
  },
  public_benefit: {
    label: 'Public benefit',
    plural: 'public benefit documents',
    Icon: FaHandHoldingHeart,
    tile: 'bg-teal-50 text-teal-700',
    chip: 'bg-teal-50 text-teal-700 border-teal-200/60',
    shown: true,
  },
  remedy_offer: {
    label: 'Remedy offer',
    plural: 'remedy offers',
    Icon: FaHandshake,
    tile: 'bg-emerald-50 text-emerald-700',
    chip: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
    shown: true,
  },
  remedy_questionnaire: {
    label: 'Remedy consultation',
    plural: 'remedy consultations',
    Icon: FaRegComments,
    tile: 'bg-emerald-50 text-emerald-700',
    chip: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
    shown: true,
  },
  phase_2_consultation: {
    label: 'Phase 2 consultation',
    plural: 'phase 2 consultations',
    Icon: FaRegComments,
    tile: 'bg-blue-50 text-blue-600',
    chip: 'bg-blue-50 text-blue-700 border-blue-200/60',
    shown: true,
  },
  materially_incomplete: {
    label: 'Materially incomplete',
    plural: 'notifications held materially incomplete',
    Icon: FaCircleExclamation,
    tile: 'bg-orange-50 text-orange-700',
    chip: 'bg-orange-50 text-orange-700 border-orange-200/60',
    shown: true,
  },
  notification_completed: {
    label: 'Notification completed',
    plural: 'notifications completed',
    Icon: FaCircleCheck,
    tile: 'bg-primary/10 text-primary',
    chip: 'bg-primary/5 text-primary border-primary/20',
    shown: true,
  },
  timeline_extension: {
    label: 'Timeline extended',
    plural: 'timeline extensions',
    Icon: FaHourglassHalf,
    tile: 'bg-sky-50 text-sky-700',
    chip: 'bg-sky-50 text-sky-700 border-sky-200/60',
    shown: true,
  },
  other: {
    label: 'Other',
    plural: 'other events',
    Icon: FaCircleInfo,
    tile: 'bg-gray-100 text-gray-600',
    chip: 'bg-gray-50 text-gray-700 border-gray-200/60',
    shown: true,
  },
  // Hidden: already on the dashboard's cards, or routine.
  phase_1_determination: {
    label: 'Phase 1 determination',
    plural: 'phase 1 determinations',
    Icon: FaGavel,
    tile: 'bg-purple-50 text-purple-600',
    chip: 'bg-purple-50 text-purple-700 border-purple-200/60',
    shown: false,
  },
  waiver_determination: {
    label: 'Waiver determination',
    plural: 'waiver determinations',
    Icon: FaStamp,
    tile: 'bg-gray-100 text-gray-600',
    chip: 'bg-gray-50 text-gray-700 border-gray-200/60',
    shown: false,
  },
  notified: {
    label: 'Notified',
    plural: 'notifications',
    Icon: FaCirclePlus,
    tile: 'bg-primary/10 text-primary',
    chip: 'bg-primary/5 text-primary border-primary/20',
    shown: false,
  },
  questionnaire: {
    label: 'Consultation',
    plural: 'consultations',
    Icon: FaRegComments,
    tile: 'bg-blue-50 text-blue-600',
    chip: 'bg-blue-50 text-blue-700 border-blue-200/60',
    shown: false,
  },
};

const TYPE_ORDER = Object.keys(RECENT_EVENT_TYPES);

// A type the frontend doesn't know yet (the classifier grew one before this
// file did) reads as "Other" rather than disappearing.
export const getRecentEventType = (type) => RECENT_EVENT_TYPES[type] || RECENT_EVENT_TYPES.other;

export const isRecentEventShown = (event) => getRecentEventType(event.type).shown;

// Position in significance order; unknown types sort with "other".
export const recentEventRank = (type) => {
  const index = TYPE_ORDER.indexOf(type);
  return index === -1 ? TYPE_ORDER.indexOf('other') : index;
};
