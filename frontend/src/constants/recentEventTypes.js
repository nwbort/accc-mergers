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
// event is). `shown` decides whether the dashboard's "Recent events" table
// lists it: the feed publishes every type, so narrowing the table is a matter
// of flipping a flag here, not of regenerating the data.
//
// Tile/chip colours follow UpcomingEventsTimeline's: a pale fill with the
// family's dark text, so each chip clears AA as small text. Full class strings
// keep Tailwind's scanner happy.
export const RECENT_EVENT_TYPES = {
  notified: {
    label: 'Notified',
    Icon: FaCirclePlus,
    tile: 'bg-primary/10 text-primary',
    chip: 'bg-primary/5 text-primary border-primary/20',
    shown: true,
  },
  materially_incomplete: {
    label: 'Materially incomplete',
    Icon: FaCircleExclamation,
    tile: 'bg-orange-50 text-orange-700',
    chip: 'bg-orange-50 text-orange-700 border-orange-200/60',
    shown: true,
  },
  notification_completed: {
    label: 'Notification completed',
    Icon: FaCircleCheck,
    tile: 'bg-primary/10 text-primary',
    chip: 'bg-primary/5 text-primary border-primary/20',
    shown: true,
  },
  questionnaire: {
    label: 'Consultation',
    Icon: FaRegComments,
    tile: 'bg-blue-50 text-blue-600',
    chip: 'bg-blue-50 text-blue-700 border-blue-200/60',
    shown: true,
  },
  timeline_extension: {
    label: 'Timeline extended',
    Icon: FaHourglassHalf,
    tile: 'bg-sky-50 text-sky-700',
    chip: 'bg-sky-50 text-sky-700 border-sky-200/60',
    shown: true,
  },
  phase_1_determination: {
    label: 'Phase 1 determination',
    Icon: FaGavel,
    tile: 'bg-purple-50 text-purple-600',
    chip: 'bg-purple-50 text-purple-700 border-purple-200/60',
    shown: true,
  },
  phase_2_referral: {
    label: 'Phase 2 referral',
    Icon: FaArrowRight,
    tile: 'bg-amber-50 text-amber-700',
    chip: 'bg-amber-50 text-amber-700 border-amber-200/60',
    shown: true,
  },
  competition_concerns: {
    label: 'Concerns notice',
    Icon: FaTriangleExclamation,
    tile: 'bg-amber-50 text-amber-700',
    chip: 'bg-amber-50 text-amber-700 border-amber-200/60',
    shown: true,
  },
  remedy_offer: {
    label: 'Remedy offer',
    Icon: FaHandshake,
    tile: 'bg-emerald-50 text-emerald-700',
    chip: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
    shown: true,
  },
  remedy_questionnaire: {
    label: 'Remedy consultation',
    Icon: FaRegComments,
    tile: 'bg-emerald-50 text-emerald-700',
    chip: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
    shown: true,
  },
  undertaking_accepted: {
    label: 'Undertaking accepted',
    Icon: FaFileSignature,
    tile: 'bg-emerald-50 text-emerald-700',
    chip: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
    shown: true,
  },
  phase_2_determination: {
    label: 'Phase 2 determination',
    Icon: FaGavel,
    tile: 'bg-purple-50 text-purple-600',
    chip: 'bg-purple-50 text-purple-700 border-purple-200/60',
    shown: true,
  },
  reasons: {
    label: 'Reasons',
    Icon: FaFileLines,
    tile: 'bg-purple-50 text-purple-600',
    chip: 'bg-purple-50 text-purple-700 border-purple-200/60',
    shown: true,
  },
  public_benefit: {
    label: 'Public benefit',
    Icon: FaHandHoldingHeart,
    tile: 'bg-teal-50 text-teal-700',
    chip: 'bg-teal-50 text-teal-700 border-teal-200/60',
    shown: true,
  },
  ceased: {
    label: 'Ceased',
    Icon: FaBan,
    tile: 'bg-gray-100 text-gray-600',
    chip: 'bg-gray-50 text-gray-700 border-gray-200/60',
    shown: true,
  },
  waiver_determination: {
    label: 'Waiver determination',
    Icon: FaStamp,
    tile: 'bg-gray-100 text-gray-600',
    chip: 'bg-gray-50 text-gray-700 border-gray-200/60',
    shown: true,
  },
  tribunal: {
    label: 'Tribunal',
    Icon: FaScaleBalanced,
    tile: 'bg-indigo-50 text-indigo-700',
    chip: 'bg-indigo-50 text-indigo-700 border-indigo-200/60',
    shown: true,
  },
  federal_court: {
    label: 'Federal Court',
    Icon: FaLandmark,
    tile: 'bg-indigo-50 text-indigo-700',
    chip: 'bg-indigo-50 text-indigo-700 border-indigo-200/60',
    shown: true,
  },
  other: {
    label: 'Other',
    Icon: FaCircleInfo,
    tile: 'bg-gray-100 text-gray-600',
    chip: 'bg-gray-50 text-gray-700 border-gray-200/60',
    shown: true,
  },
};

// A type the frontend doesn't know yet (the classifier grew one before this
// table did) reads as "Other" rather than disappearing.
export const getRecentEventType = (type) => RECENT_EVENT_TYPES[type] || RECENT_EVENT_TYPES.other;

export const isRecentEventShown = (event) => getRecentEventType(event.type).shown;
