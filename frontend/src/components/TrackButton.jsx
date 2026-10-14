import BellIcon from './BellIcon';
import { HEADER_BUTTON_BASE, HEADER_BUTTON_VARIANTS } from '../constants/headerButton';

function TrackButton({
  active,
  onClick,
  activeLabel,
  inactiveLabel,
  activeAriaLabel,
  inactiveAriaLabel,
  title,
  onDark = false,
}) {
  const variant = onDark ? HEADER_BUTTON_VARIANTS.dark : HEADER_BUTTON_VARIANTS.light;

  return (
    <button
      onClick={onClick}
      className={`${HEADER_BUTTON_BASE} ${
        active ? variant.active : variant.inactive
      } ${variant.focus || ''}`}
      aria-pressed={active}
      aria-label={active ? activeAriaLabel : inactiveAriaLabel}
      title={title}
    >
      <BellIcon filled={active} className="w-3.5 h-3.5" />
      {active ? activeLabel : inactiveLabel}
    </button>
  );
}

export default TrackButton;
