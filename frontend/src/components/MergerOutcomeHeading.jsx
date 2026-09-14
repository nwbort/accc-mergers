import { FaGavel } from 'react-icons/fa';
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
 * The line carries two kinds of thing. What merely qualifies the standing — a
 * conditional clearance, the result of a concluded appeal — rides on it as a
 * chip. A live appeal does not: the ACCC's position still stands while the
 * Tribunal looks at it, so the matter is carrying two statuses at once, and the
 * second is set exactly like the first (gavel included) rather than shrunk into
 * a chip beside it. That holds whether the matter underneath is decided or
 * still running.
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
    <p className={`flex items-center gap-x-4 gap-y-2 flex-wrap mb-2 text-sm font-bold uppercase tracking-widest ${style.heading}`}>
      <span className="inline-flex items-center gap-2">
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
        {/* These two qualify the outcome rather than standing beside it —
            "approved, but with conditions" — so they stay chips hanging off it. */}
        {showConditions && <span className={chip}>with conditions</span>}
        {appealSuffix && <span className={chip}>{appealSuffix}</span>}
      </span>
      {/* A live appeal is a status in its own right, not a qualifier: the ACCC's
          position stands, and the Tribunal's is a second thing the matter is
          carrying. So it is set like the status beside it rather than shrunk
          into a chip. */}
      {merger.under_appeal && (
        <span className="inline-flex items-center gap-2">
          {/* The gavel stands where the outcome's glyph does, so the two read as
              a matched pair. A live status has no glyph to match, so there is
              nothing to balance and a dot does the separating instead — without
              it two same-styled phrases run together. */}
          {Icon ? (
            // A shade larger than the outcome glyph beside it: the gavel sits
            // on the diagonal with white space in its box, so at a matching
            // w-3.5 it reads lighter than the tick or cross it is paired with.
            <FaGavel className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
          ) : (
            <span aria-hidden="true">·</span>
          )}
          <span>Under appeal</span>
        </span>
      )}
    </p>
  );
}

export default MergerOutcomeHeading;
