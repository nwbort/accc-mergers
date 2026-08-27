import BellIcon from './BellIcon';

function TrackButton({
  active,
  onClick,
  activeLabel,
  inactiveLabel,
  activeAriaLabel,
  inactiveAriaLabel,
  title,
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center justify-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg border transition-all duration-200 flex-shrink-0 ${
        active
          ? 'bg-primary text-white border-primary hover:bg-primary-dark shadow-sm'
          : 'bg-gray-100 text-gray-600 border-gray-200/60 hover:bg-gray-200'
      }`}
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
