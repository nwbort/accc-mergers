import { MERGER_STATUS } from '../constants/mergerStatus';
import { getOutcomeHeaderStyle } from '../constants/outcomeHeader';
import { OUTCOME_ICONS } from '../constants/outcomeIcons';
import { getHeaderStatus } from '../utils/mergerOutcome';
import Phase2OddsReveal from './Phase2OddsReveal';

/**
 * The line above a merger's title, sitting on the colour-filled header block
 * the detail page paints around it. It states where the matter stands in the
 * register's own words — the outcome once it is decided, the status it is
 * sitting at until then. On a decided matter the deep fill behind it does the
 * shouting and the line inherits its white; on a live one the fill is a pale
 * tint and the line carries the status colour itself. Either way it stays a
 * small eyebrow rather than competing with the h1.
 *
 * Everything that qualifies that standing rides here as a chip: a conditional
 * clearance, the result of a concluded appeal, and a live appeal. An appeal is
 * an additional status rather than a different one — the ACCC's own position
 * still stands while the Tribunal looks at it — so it reads the same way here
 * whether the matter underneath is decided or still running.
 */
function MergerOutcomeHeading({ merger }) {
  const headerStatus = getHeaderStatus(merger);
  if (!headerStatus) return null;

  const { label, appealSuffix, decided } = headerStatus;
  const style = getOutcomeHeaderStyle(label);
  // Only decided outcomes have a glyph — a live matter has no result to
  // symbolise, and a made-up one would read as having got a result
  // (constants/outcomeIcons.js).
  const Icon = OUTCOME_ICONS[label] ?? null;

  // Mirrors StatusBadge: a stale conditions flag on any other outcome stays
  // hidden rather than reading as a conditional clearance.
  const showConditions =
    Boolean(merger.has_conditions) && merger.accc_determination === MERGER_STATUS.APPROVED;

  const chip = `inline-flex items-center px-1.5 py-0.5 rounded normal-case tracking-normal text-[11px] font-medium ${style.chip}`;

  return (
    <p className={`flex items-center gap-2 flex-wrap mb-2 text-sm font-bold uppercase tracking-widest ${style.heading}`}>
      {Icon && <Icon className="w-3.5 h-3.5 flex-shrink-0" aria-hidden="true" />}
      {/* Without this the line reads as a bare adjective ahead of the merger's
          name. A determination and a live status are different claims, so they
          are not introduced with the same word. */}
      <span className="sr-only">{decided ? 'Outcome:' : 'Status:'}</span>
      {/* The press-and-hold phase 2 odds sit on the live status, which is what
          this line now carries; the wrapper is inert for every other matter. */}
      <Phase2OddsReveal merger={merger}>
        <span>{label}</span>
      </Phase2OddsReveal>
      {showConditions && <span className={chip}>with conditions</span>}
      {appealSuffix && <span className={chip}>{appealSuffix}</span>}
      {merger.under_appeal && <span className={chip}>under appeal</span>}
    </p>
  );
}

export default MergerOutcomeHeading;
