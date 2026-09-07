/**
 * The promo banner the dashboard is currently running, or null to run none.
 *
 * Everything that makes a campaign a campaign lives here; PromoCard just
 * renders it. To switch the banner to a different page, rewrite this object -
 * and give `campaign` a new id, because it keys the localStorage dismissal so
 * a new id brings the card back for everyone who dismissed the previous one.
 */

import { FaGaugeHigh } from 'react-icons/fa6';

export const DASHBOARD_PROMO = {
  campaign: 'current-status-v1',
  to: '/current-status',
  icon: FaGaugeHigh,
  title: 'How fast is the ACCC deciding mergers right now?',
  description: 'See recent waiver and phase 1 decision times against the all-time baseline.',
};
