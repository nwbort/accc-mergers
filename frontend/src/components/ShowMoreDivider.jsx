import { FaChevronDown } from 'react-icons/fa6';

// A thin horizontal rule with the toggle label set in the middle of the line,
// in place of a standalone button. The label's background matches the page
// (slate-50, #f8fafc) so the rule appears to pass behind the text.
function ShowMoreDivider({ expanded, onToggle, className = '' }) {
  return (
    <div className={`relative my-5 ${className}`}>
      <div className="absolute inset-0 flex items-center" aria-hidden="true">
        <div className="w-full border-t border-gray-200" />
      </div>
      <div className="relative flex justify-center">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="inline-flex items-center gap-1.5 bg-slate-50 px-3 text-sm font-medium text-gray-500 transition-colors hover:text-primary"
        >
          {expanded ? 'Show less' : 'Show more'}
          <FaChevronDown
            className={`h-3 w-3 transition-transform ${expanded ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
        </button>
      </div>
    </div>
  );
}

export default ShowMoreDivider;
