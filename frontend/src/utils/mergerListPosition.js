/**
 * Where the reader was in the merger list, so coming back to it lands them
 * there again rather than at the top with only the first 50 shown.
 *
 * Kept in sessionStorage (one tab's history, like the filter params beside it)
 * and tied to the exact search params it was saved under: the depth and offset
 * only mean anything for the list they were measured on.
 */

const POSITION_KEY = 'mergers_list_position';

/**
 * Router `state` for a link back to the list that should restore the
 * position, as a Back button would. The detail page's "Back to all mergers"
 * link carries it; an ordinary link to /mergers starts at the top.
 */
export const RESTORE_LIST_POSITION_STATE = { restoreListPosition: true };

/**
 * @param {string} params - The list's search params, as `URLSearchParams.toString()`
 * @param {number} page - How many 50-merger pages were showing
 * @param {number} y - window.scrollY
 */
export function saveListPosition(params, page, y) {
  try {
    sessionStorage.setItem(POSITION_KEY, JSON.stringify({ params, page, y }));
  } catch {
    // Storage blocked or full — the list just opens at the top next time.
  }
}

/**
 * The saved `{ page, y }` for a list showing `params`, or null when nothing
 * was saved for that list.
 */
export function loadListPosition(params) {
  try {
    const saved = JSON.parse(sessionStorage.getItem(POSITION_KEY));
    if (!saved || saved.params !== params) return null;
    const page = Number(saved.page);
    const y = Number(saved.y);
    if (!Number.isInteger(page) || page < 1 || !Number.isFinite(y)) return null;
    return { page, y };
  } catch {
    return null;
  }
}
