/**
 * Stands in for a date a materially incomplete notification doesn't have yet.
 *
 * When the ACCC decides under s 51ABZ that a notification is materially
 * incomplete (merger.materially_incomplete, set by the pipeline), it has no
 * effective notification date, and the end of determination period the
 * register still shows was computed from the original lodgement — the clock
 * only starts once the parties fill the gap. Both dates are pending, and this
 * says why. Italic and muted so it doesn't read as a date.
 */
export const MATERIALLY_INCOMPLETE_LABEL = 'Pending – materially incomplete';

function MateriallyIncompletePending({ className = '' }) {
  return (
    <span className={`italic font-normal text-gray-500 ${className}`.trim()}>
      {MATERIALLY_INCOMPLETE_LABEL}
    </span>
  );
}

export default MateriallyIncompletePending;
