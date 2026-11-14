import { FaChevronDown } from 'react-icons/fa6';

// A thin horizontal rule with the toggle set in the middle of the line: an
// M3 tonal button, whose pill sits over the rule.
function ShowMoreDivider({ expanded, onToggle, className = '' }) {
  return (
    <div className={`relative my-5 ${className}`}>
      <div className="absolute inset-0 flex items-center" aria-hidden="true">
        <div className="w-full border-t border-outline-variant" />
      </div>
      <div className="relative flex justify-center">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="press-morph inline-flex items-center gap-1.5 h-10 rounded-full bg-secondary-container px-5 text-sm font-semibold text-on-secondary-container ring-4 ring-surface-container-low hover:shadow-card-hover"
        >
          {expanded ? 'Show less' : 'Show more'}
          <FaChevronDown
            className={`h-3 w-3 transition-transform duration-300 ease-spring ${expanded ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
        </button>
      </div>
    </div>
  );
}

export default ShowMoreDivider;
