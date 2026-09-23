import { FaGavel } from 'react-icons/fa';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { getOutcomeHeaderStyle } from '../constants/outcomeHeader';
import { OUTCOME_ICONS } from '../constants/outcomeIcons';
import { getHeaderStatus, getPublicBenefitQualifier } from '../utils/mergerOutcome';
import Phase2OddsReveal from './Phase2OddsReveal';
import WaiverBadge from './WaiverBadge';

/**
 * The line above a merger's title, sitting on the colour-filled header block
 * the detail page paints around it. It states where the matter stands in the
 * register's own words — the outcome once it is decided, the status it is
 * sitting at until then. On a decided matter the deep fill behind it does the
 * shouting and the line inherits its white; on a live one the fill is a pale
 * tint and the line carries the status colour itself. Either way it stays a
 * small eyebrow rather than competing with the h1.
 *
 * The line carries two kinds of thing, and nothing on it is shrunk. What merely
 * qualifies the standing — a conditional clearance, the result of a concluded
 * appeal — is folded into its run of text, because those are part of what the
 * outcome is rather than notes about it. A live appeal is not a qualifier at
 * all: the ACCC's position still stands while the Tribunal looks at it, so the
 * matter is carrying two statuses at once, and the second is set exactly like
 * the first, gavel included. That holds whether the matter underneath is
 * decided or still running.
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

  // Qualifiers are part of what the outcome *is*, so they are set in its type
  // and sit in its own run of text rather than being boxed off beside it.
  // "Approved with conditions" is the outcome's own name (see
  // MERGER_STATUS.APPROVED_WITH_CONDITIONS); a concluded appeal's result takes
  // a dot, since "Not approved confirmed on appeal" would read as one phrase.
  // An outcome reached in the public benefit phase says so, the same way.
  const publicBenefit = getPublicBenefitQualifier(merger);
  const outcome =
    `${label}${showConditions ? ' with conditions' : ''}${publicBenefit ? ` · ${publicBenefit}` : ''}${appealSuffix ? ` · ${appealSuffix}` : ''}`;

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
          <span>{outcome}</span>
        </Phase2OddsReveal>
      </span>
      {/* A live appeal is a status in its own right, not a qualifier: the ACCC's
          position stands, and the Tribunal's is a second thing the matter is
          carrying. So it is set like the status beside it rather than shrunk
          into a chip. */}
      {merger.under_appeal && (
        <span className="inline-flex items-center gap-2">
          {/* The gavel is the appeal's own glyph, worn wherever it appears —
              here and on the list card's badge — the way a tick belongs to an
              approval. It also does the separating a status set in the same
              type as the one beside it would otherwise need, including where
              that one is a live status carrying no glyph of its own.

              A shade larger than the outcome glyph beside it: the gavel sits on
              the diagonal with white space in its box, so at a matching w-3.5 it
              reads lighter than the tick or cross it is paired with. */}
          <FaGavel className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
          <span>Under appeal</span>
        </span>
      )}
      {/* A type flag rather than a status, so — unlike the outcome and the
          appeal above — it wears a chip rather than being set in the line's
          own type. Solid so it reads the same badge as everywhere else on the
          site (merger list, Commentary, industry cards), and because that
          form fills its own box rather than relying on the fill it sits on. */}
      {merger.is_waiver && <WaiverBadge solid />}
    </p>
  );
}

export default MergerOutcomeHeading;
