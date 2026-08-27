import { FaBell, FaRegBell } from 'react-icons/fa';

function BellIcon({ filled = false, className = "w-4 h-4" }) {
  const Icon = filled ? FaBell : FaRegBell;
  return <Icon className={className} aria-hidden="true" />;
}

export default BellIcon;
