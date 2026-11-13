import StatusGlyph from './StatusGlyph';
import WaiverBadge from './WaiverBadge';
import AppealBadge from './AppealBadge';
import JudicialReviewBadge from './JudicialReviewBadge';
import RefiledBadge from './RefiledBadge';
import MateriallyIncompleteBadge from './MateriallyIncompleteBadge';
import { resolveStatusDisplay } from '../utils/statusDisplay';

/**
 * What a merger card shows, after the Android app's MergerCard (ui/Common.kt):
 * the outcome leading as its Material shape (StatusGlyph) and in words, the
 * flags a matter carries riding on the same line so a flagged card is no
 * taller, then the name, then one line of identifiers and dates (`meta`, a
 * list of nodes joined with middots).
 *
 * The wrapper (a link, tinted with getOutcomeCardTint) belongs to the caller:
 * MergerListCard on /mergers, IndustryMergerGroups on the industry and party
 * pages. `trailing` sits at the end of the status line (the list's Track
 * button).
 */
function MergerCardFace({ status, determination, hasConditions, appeal, flags = {}, name, Heading = 'h2', meta = [], trailing = null }) {
  const statusInput = { status, determination, hasConditions, appeal };
  const { displayText, showConditions, appealSuffix } = resolveStatusDisplay(statusInput);
  const parts = meta.filter(Boolean);
  return (
    <>
      <div className="flex items-center gap-2.5">
        <StatusGlyph {...statusInput} decorative />
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5 gap-y-1">
          <span className="text-sm font-bold text-gray-900">
            {displayText}
            {showConditions && <span className="font-medium"> · with conditions</span>}
            {appealSuffix && <span className="font-medium"> · {appealSuffix}</span>}
          </span>
          {flags.underAppeal && <AppealBadge solid />}
          {flags.underJudicialReview && <JudicialReviewBadge solid />}
          {flags.waiver && <WaiverBadge solid />}
          {flags.refiled && <RefiledBadge solid />}
          {flags.materiallyIncomplete && <MateriallyIncompleteBadge solid />}
        </div>
        {trailing}
      </div>
      <Heading className="mt-2.5 text-base font-semibold leading-snug tracking-tight text-gray-900 group-hover:text-primary">
        {name}
      </Heading>
      {parts.length > 0 && (
        // Each part carries the dot after it rather than before, so a line
        // that wraps ends on a dot instead of starting with one.
        <p className="mt-1.5 flex flex-wrap gap-x-1.5 text-xs text-gray-600">
          {parts.map((part, i) => (
            <span key={i} className="inline-flex gap-x-1.5">
              {part}
              {i < parts.length - 1 && <span aria-hidden="true">·</span>}
            </span>
          ))}
        </p>
      )}
    </>
  );
}

export default MergerCardFace;
