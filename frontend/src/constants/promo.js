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

import { FaFileLines } from 'react-icons/fa6';
import { eventAnchorId } from '../utils/eventAnchor';
import { mergerPath } from '../utils/slug';

// The ACCC's FOI release on Imagine Education's childcare restructure waiver
// (WA-80019, FOI request 100473/2026-2027). Links to the first of its
// documents in the detail page's event list - the waiver application's
// parties and Part A responses - whose anchor opens the collapsed FOI run and
// scrolls to that row. Built from the event as the detail file carries it, so
// the anchor matches the row's id.
const IMAGINE_EDUCATION_FOI_EVENT = {
  date: '2026-10-20T12:00:00Z',
  display_title: 'FOI release \u2013 Waiver application \u2013 parties and Part A responses (acquisitions portal)',
};

export const IMAGINE_EDUCATION_FOI_PROMO = {
  campaign: 'imagine-education-foi-waiver-application',
  to: `${mergerPath('WA-80019', 'Imagine Education \u2013 childcare centres ownership restructure')}#${eventAnchorId(IMAGINE_EDUCATION_FOI_EVENT)}`,
  icon: FaFileLines,
  title: 'Released under FOI: Imagine Education\'s waiver application',
  description: 'Read the documents submitted to the ACCC',
};

export const DASHBOARD_PROMOS = [
  IMAGINE_EDUCATION_FOI_PROMO,
];
