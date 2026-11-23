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
 *
 * A campaign links either inside the site (`to`) or out of it (`href`, opened
 * in a new tab). One whose wording changes with the clock carries
 * `resolve(now)`, returning the props to show at `now` (merged over the
 * campaign's own) or null to hide it; PromoStack re-reads it every minute.
 */

import { FaArrowRightArrowLeft } from 'react-icons/fa6';

// Waivers the ACCC declined that came back as formal notifications. Links to
// the /refiled-notifications page (nav label "Refiled waivers").
export const REFILED_WAIVERS_PROMO = {
  campaign: 'refiled-waivers',
  to: '/refiled-notifications',
  icon: FaArrowRightArrowLeft,
  title: 'Declined waiver? Often not the end of the road',
  description: 'See which waivers were re-filed as notifications, and how they fared',
};

export const DASHBOARD_PROMOS = [
  REFILED_WAIVERS_PROMO,
];
