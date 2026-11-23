import { useState } from 'react';
import ShowMoreDivider from './ShowMoreDivider';

// Shared responsive card grid with a collapse/expand control. Fewer cards show
// on mobile (single-column, where the list is a tall scroll) than from `sm` up.
// Every card is rendered and the overflow is gated with CSS so the visible
// count can differ per breakpoint; the divider only appears when there is
// something to toggle at the current breakpoint. Callers can raise either
// count (the Phase 2 page shows nine completed matters from `sm` up).
const DEFAULT_VISIBLE_MOBILE = 3;
const DEFAULT_VISIBLE_DESKTOP = 6;

function CardCollapseGrid({
  items,
  getKey,
  getStyle,
  renderBody,
  visibleMobile = DEFAULT_VISIBLE_MOBILE,
  visibleDesktop = DEFAULT_VISIBLE_DESKTOP,
}) {
  const [expanded, setExpanded] = useState(false);

  const moreOnMobile = items.length > visibleMobile;
  const moreOnDesktop = items.length > visibleDesktop;

  const visibilityClass = (index) => {
    if (expanded) return 'flex';
    if (index < visibleMobile) return 'flex';
    if (index < visibleDesktop) return 'hidden sm:flex';
    return 'hidden';
  };

  return (
    <>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item, index) => {
          const style = getStyle(item);
          return (
            <li
              key={getKey(item, index)}
              className={`relative ${visibilityClass(index)} min-h-[7rem] flex-col justify-between rounded-xl p-4 transition-colors ${style.bg} ${style.text} ${style.border || ''}`}
            >
              {renderBody(item, style)}
            </li>
          );
        })}
      </ul>
      {moreOnMobile && (
        <ShowMoreDivider
          expanded={expanded}
          onToggle={() => setExpanded((prev) => !prev)}
          className={moreOnDesktop ? '' : 'sm:hidden'}
        />
      )}
    </>
  );
}

export default CardCollapseGrid;
