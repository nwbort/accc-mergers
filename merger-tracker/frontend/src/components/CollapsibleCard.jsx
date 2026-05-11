import { useId, useState } from 'react';
import { FaChevronDown } from 'react-icons/fa';

function CollapsibleCard({ icon, iconBgClass = 'bg-gray-100', title, subtitle, onExpand, children }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const panelId = useId();

  const handleToggle = () => {
    const next = !isExpanded;
    setIsExpanded(next);
    if (next && onExpand) onExpand();
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card mb-6 overflow-hidden">
      <button
        type="button"
        onClick={handleToggle}
        className="w-full text-left p-6 flex items-center justify-between gap-4 hover:bg-gray-50/50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
        aria-expanded={isExpanded}
        aria-controls={panelId}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center ${iconBgClass}`}>
            {icon}
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">
              {title}
            </h2>
            {subtitle && (
              <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>
            )}
          </div>
        </div>
        <FaChevronDown
          className={`w-5 h-5 text-gray-400 flex-shrink-0 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {isExpanded && (
        <div id={panelId} className="px-6 pb-6 border-t border-gray-100">
          {children}
        </div>
      )}
    </div>
  );
}

export default CollapsibleCard;
