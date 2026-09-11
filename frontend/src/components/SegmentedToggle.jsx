/**
 * Pill-shaped segmented control: a row of mutually exclusive options in a grey
 * track, the selected one lifted onto a white chip.
 *
 * Analysis (business vs calendar days) and CurrentStatus (the rolling window)
 * each grew their own copy of this markup, and the two had already drifted on
 * labelling. Both now render this, so the control reads the same wherever it
 * appears.
 */
function SegmentedToggle({ ariaLabel, options, value, onChange }) {
  return (
    <div
      className="inline-flex items-center bg-gray-100 rounded-full p-0.5 text-sm"
      role="group"
      aria-label={ariaLabel}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={String(option.value)}
            type="button"
            onClick={() => onChange(option.value)}
            aria-pressed={selected}
            className={`px-3.5 py-1.5 rounded-full font-medium transition-all duration-150 ${
              selected
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
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
