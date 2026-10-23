/**
 * The promo banners the dashboard runs, in priority order.
 *
 * Everything that makes a campaign a campaign lives here; PromoStack stacks
 * every one the reader hasn't dismissed, top to bottom in this order, and the
 * rest move up when they dismiss one. Empty the list to run none.
 *
 * `campaign` keys the localStorage dismissal. To point a banner at something
 * new, give it a new id, so it comes back for everyone who dismissed the old
 * one; reusing an id keeps it hidden from them.
 */

import { FaGaugeHigh, FaFileLines } from 'react-icons/fa6';

export const DASHBOARD_PROMOS = [
  {
    campaign: 'current-status-v1',
    to: '/current-status',
    icon: FaGaugeHigh,
    title: 'How fast is the ACCC deciding mergers right now?',
    description: 'See recent waiver and phase 1 decision times against the all-time baseline.',
  },
  {
    // Names its quarter, so a new quarter wants a new id, link and title.
    campaign: 'quarterly-report-26Q3',
    to: '/quarterly/26Q3',
    icon: FaFileLines,
    title: 'The Q3 2026 merger report is out',
    description: 'Volumes, clearance rates, timing and Tribunal reviews in our quarterly report.',
  },
];
