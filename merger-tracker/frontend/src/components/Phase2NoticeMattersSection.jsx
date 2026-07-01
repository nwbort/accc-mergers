import { FaSearch } from 'react-icons/fa';
import CollapsibleCard from './CollapsibleCard';
import ExternalLinkIcon from './ExternalLinkIcon';

const MattersIcon = () => (
  <FaSearch className="h-5 w-5 text-amber-600" aria-hidden="true" />
);

// Find the event carrying the parsed "Matters the ACCC intends to
// investigate in Phase 2" boxes from the Phase 2 Notice PDF. A matter can
// only have one live Phase 2 Notice event at a time, so the first match wins.
function findPhase2NoticeEvent(events) {
  return events.find(
    (e) => Array.isArray(e.phase2_notice_matters_to_investigate) && e.phase2_notice_matters_to_investigate.length > 0
  );
}

function Phase2NoticeMattersSection({ merger }) {
  const eventsArr = merger?.events || [];
  const event = findPhase2NoticeEvent(eventsArr);

  if (!event) return null;

  const boxes = event.phase2_notice_matters_to_investigate;

  return (
    <CollapsibleCard
      icon={<MattersIcon />}
      iconBgClass="bg-amber-100"
      title="Matters the ACCC Intends to Investigate"
      subtitle="Click to view the areas the ACCC flagged for further investigation in Phase 2"
    >
      <div className="mt-4">
        {event.url_gh && (
          <div className="mb-4">
            <a
              href={event.url_gh}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary-dark transition-colors font-medium"
            >
              View Phase 2 Notice document
              <ExternalLinkIcon className="h-3 w-3" />
              <span className="sr-only">(opens in new tab)</span>
            </a>
          </div>
        )}
        <div className="space-y-5">
          {boxes.map((box, idx) => (
            <div key={idx}>
              {box.heading && (
                <h3 className="text-sm font-semibold text-gray-900 mb-2">{box.heading}</h3>
              )}
              <ul className="list-disc list-outside pl-5 space-y-1.5">
                {box.items.map((item, j) => (
                  <li key={j} className="text-sm text-gray-600 leading-relaxed">{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </CollapsibleCard>
  );
}

export default Phase2NoticeMattersSection;
