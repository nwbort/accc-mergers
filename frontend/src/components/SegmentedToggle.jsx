/**
 * A row of mutually exclusive options, as Material 3 Expressive's connected
 * button group: pills set side by side with a small gap, their inner corners
 * squared, and the selected one filled and morphing to a full pill.
 *
 * Analysis (business vs calendar days) and CurrentStatus (the rolling window)
 * each grew their own copy of this markup, and the two had already drifted on
 * labelling. Both now render this, so the control reads the same wherever it
 * appears.
 */
function SegmentedToggle({ ariaLabel, options, value, onChange }) {
  const last = options.length - 1;
  return (
    <div
      className="inline-flex items-center gap-0.5 text-sm"
      role="group"
      aria-label={ariaLabel}
    >
      {options.map((option, index) => {
        const selected = option.value === value;
        // Outer ends stay round; inner corners square off to join the group.
        // The selected button rounds every corner.
        const shape = selected
          ? 'rounded-full'
          : `${index === 0 ? 'rounded-l-full' : 'rounded-l-md'} ${index === last ? 'rounded-r-full' : 'rounded-r-md'}`;
        return (
          <button
            key={String(option.value)}
            type="button"
            onClick={() => onChange(option.value)}
            aria-pressed={selected}
            className={`press-morph h-9 px-3.5 sm:px-4 font-semibold whitespace-nowrap ${shape} ${
              selected
                ? 'bg-primary text-white'
                : 'bg-surface-container-high text-gray-700 hover:bg-surface-container-highest hover:text-gray-900'
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export default SegmentedToggle;
