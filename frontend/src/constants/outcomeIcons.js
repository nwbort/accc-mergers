/**
 * Determination outcome -> the glyph that stands for it.
 *
 * Shared by the detail page's outcome heading and StatusBadge so the same
 * result never gets a tick in one place and a cross in another. It also means
 * an outcome is carried by shape as well as by colour, which is what keeps the
 * badges off colour-alone (WCAG 1.4.1) once they are scanned in a list.
 *
 * Only decided outcomes appear here. A matter still under assessment has no
 * result to symbolise, and a made-up glyph for it would read as one.
 */

import { FaBan, FaCheck, FaTimes } from 'react-icons/fa';
import { MERGER_STATUS } from './mergerStatus';

export const OUTCOME_ICONS = {
  [MERGER_STATUS.APPROVED]: FaCheck,
  [MERGER_STATUS.NOT_OPPOSED]: FaCheck,
  [MERGER_STATUS.NOT_APPROVED]: FaTimes,
  [MERGER_STATUS.DECLINED]: FaTimes,
  [MERGER_STATUS.ASSESSMENT_CEASED]: FaBan,
};
