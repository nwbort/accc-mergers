/**
 * Whether the reader prefers the merger list as cards or as a table.
 *
 * A personal preference rather than part of what a link shares, so it lives
 * in localStorage, not the URL: the list opens the way each reader last left
 * it, whoever's link brought them there.
 */

const VIEW_KEY = 'mergers_list_view';

export const LIST_VIEWS = ['cards', 'table'];
const DEFAULT_VIEW = 'cards';

/** The saved view, or cards when nothing usable is saved or storage is blocked. */
export function loadListView() {
  try {
    const saved = localStorage.getItem(VIEW_KEY);
    return LIST_VIEWS.includes(saved) ? saved : DEFAULT_VIEW;
  } catch {
    return DEFAULT_VIEW;
  }
}

export function saveListView(view) {
  try {
    localStorage.setItem(VIEW_KEY, view);
  } catch {
    // Storage blocked or full — the choice just lasts until the page closes.
  }
}
