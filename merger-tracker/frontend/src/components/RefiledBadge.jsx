// Flags a matter (waiver or notification) that was later re-filed as a
// separate matter — e.g. a declined waiver re-notified, or a ceased
// assessment re-filed under a new merger ID. Mirrors WaiverBadge/AppealBadge;
// colour matches the amber "related merger" link on the detail page.
function RefiledBadge({ className = '' }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200/60 ${className}`}
      role="status"
      aria-label="Subsequently refiled as a separate matter"
    >
      Refiled
    </span>
  );
}

export default RefiledBadge;
