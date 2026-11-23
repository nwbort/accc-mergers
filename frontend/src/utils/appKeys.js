// Which keys mean a reader wants the app itself, not just the page in front
// of them. main.jsx ends its wait for a prerendered page's code and data on the
// first such key: the static page's links all work without React, but its
// shortcuts (/, Ctrl+K, g-chords) and anything typed need the app. Keys that
// scroll, move focus or are a lone modifier don't count: reading the static
// page with them should leave it on screen until the page can replace it in
// full, not cut that short into a spinner.
const READING_KEYS = new Set([
  'Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'Spacebar',
  'PageUp', 'PageDown', 'Home', 'End',
  'Shift', 'Control', 'Alt', 'Meta', 'AltGraph', 'CapsLock', 'Fn', 'OS',
]);

/** True for a keydown that should start the app at once. */
export function isAppKey(event) {
  return !READING_KEYS.has(event.key);
}
