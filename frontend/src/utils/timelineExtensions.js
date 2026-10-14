/**
 * Where each timeline extension sits on the merger detail timeline.
 *
 * The register says only "Timeline extended by N business days – following
 * …": the day count and reason live in the event title, as they do for the
 * pipeline's extensions.json (scripts/generate/static_data/outputs/extensions.py,
 * whose title rules these mirror). An extension adds its days to the end of the
 * clock of the phase it was granted in, so each one is placed by rebuilding
 * that clock: phase 1 runs PHASE_1_DEADLINE_BD from notification, phase 2
 * PHASE_2_DEADLINE_BD from the day phase 1 was due, and each phase's
 * extensions stack after its base window in the order they were granted.
 * Rebuilt that way, every extended matter's deadline matches the one the
 * register publishes.
 *
 * Extensions granted in the public benefit phase aren't placed: that clock
 * starts on an application date this rule has no hold of.
 *
 * The three title rules below (isExtensionTitle, extensionBusinessDays,
 * extensionReason) are hand-copied from that Python module.
 * `fixtures/extension-title-cases.json` pins the pair together; both test
 * suites read it, so change the rules in both places and update the cases.
 */
import { addBusinessDays, parseDateOnly, toDateString } from './dates';
import { PHASE_1_DEADLINE_BD, PHASE_2_DEADLINE_BD } from '../constants/statutoryDeadlines';
import { MERGER_STATUS } from '../constants/mergerStatus';

const EXTENSION_DAYS_RE = /extended by (\d+)\s+business day/i;

/** True if an event title marks a timeline extension. */
export const isExtensionTitle = (title) => {
  if (!title) return false;
  const lower = title.toLowerCase();
  return lower.includes('extended by') || lower.includes('extend the phase 1');
};

/** The extension's length in business days, or null if the title gives none. */
export const extensionBusinessDays = (title) => {
  const match = EXTENSION_DAYS_RE.exec(title || '');
  return match ? Number(match[1]) : null;
};

/** The "following …" clause of an extension notice, trimmed for display. */
export const extensionReason = (title) => {
  const match = /following\s+(.*)$/i.exec(title || '');
  if (!match) return '';
  return match[1].replace(/\s+/g, ' ').trim().replace(/\.+$/, '');
};

const dayOf = (iso) => (iso ? iso.slice(0, 10) : null);

/**
 * The extensions on a merger, each with the stretch of the statutory clock it
 * added: `{ date, businessDays, reason, phase, from, to }`, where `from` and
 * `to` are YYYY-MM-DD strings (the deadline before and after it). Returns an
 * empty list when there are none, or when a count can't be read from a title
 * that a later placement depends on — a gap in the clock would put every
 * extension after it in the wrong place.
 */
export function getTimelineExtensions(merger) {
  const startStr = merger?.effective_notification_datetime;
  if (!startStr || merger.is_waiver) return [];

  const extensions = (merger.events || [])
    .filter((e) => e?.date && isExtensionTitle(e.title))
    .map((e, i) => ({ event: e, i }))
    // By date, then register order for notices published the same day.
    .sort((a, b) => dayOf(a.event.date).localeCompare(dayOf(b.event.date)) || a.i - b.i)
    .map(({ event }) => event);
  if (extensions.length === 0) return [];

  const phase1End = dayOf(merger.phase_1_determination_date);
  const phase2End = dayOf(merger.phase_2_determination_date);
  const wentToPhase2 = Boolean(phase1End) && (
    merger.phase_1_determination === MERGER_STATUS.REFERRED_TO_PHASE_2
    || Boolean(merger.phase_2_determination_date)
    || /phase 2/i.test(merger.stage || '')
  );

  const phaseOf = (date) => {
    if (!wentToPhase2 || date <= phase1End) return 1;
    if (!phase2End || date <= phase2End) return 2;
    return null; // public benefit phase
  };

  const byPhase = { 1: [], 2: [] };
  for (const event of extensions) {
    const phase = phaseOf(dayOf(event.date));
    if (phase === null) continue;
    byPhase[phase].push({
      date: event.date,
      businessDays: extensionBusinessDays(event.title),
      reason: extensionReason(event.title),
      phase,
    });
  }

  const start = parseDateOnly(startStr);
  const placed = [];
  // Phase 1's deadline, after its own extensions, anchors phase 2.
  let deadline = addBusinessDays(start, PHASE_1_DEADLINE_BD);
  for (const phase of [1, 2]) {
    if (phase === 2) {
      if (byPhase[2].length === 0) break;
      deadline = addBusinessDays(deadline, PHASE_2_DEADLINE_BD);
    }
    for (const ext of byPhase[phase]) {
      if (ext.businessDays == null || !deadline) return [];
      const to = addBusinessDays(deadline, ext.businessDays);
      if (!to) return [];
      placed.push({ ...ext, from: toDateString(deadline), to: toDateString(to) });
      deadline = to;
    }
  }
  return placed;
}
