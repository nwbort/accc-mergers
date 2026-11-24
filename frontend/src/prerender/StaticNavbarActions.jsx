import { FaSearch, FaBars } from 'react-icons/fa';
import BellIcon from '../components/BellIcon';
import { NAVBAR_SOCIAL_PROFILE } from '../constants/socialProfiles';

// The real Navbar's right-hand group (components/Navbar.jsx): the social link,
// search and bell, plus the menu button in its phone layout. The Navbar picks
// its layout by measuring itself, which static HTML can't, so this draws the
// two it settles on: the full one from lg up, the phone one (tighter icons,
// with the menu button) below. Same icons and classes, so nothing pops in when
// React mounts. Until then the buttons do nothing; the social link works.
const ICON_BUTTON =
  'inline-flex items-center justify-center rounded-lg text-gray-500 hover:text-gray-900 hover:bg-gray-100/80 transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

export default function StaticNavbarActions({ compact, menu }) {
  const pad = compact ? 'p-1.5' : 'p-2';
  return (
    <>
      <a
        href={NAVBAR_SOCIAL_PROFILE.href}
        target="_blank"
        rel="noopener noreferrer me"
        className={`inline-flex items-center justify-center ${pad} rounded-lg text-gray-500 ${NAVBAR_SOCIAL_PROFILE.hoverClass} hover:bg-gray-100/80 transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2`}
        aria-label={`mergers.fyi on ${NAVBAR_SOCIAL_PROFILE.name} (opens in a new tab)`}
        title={`Follow on ${NAVBAR_SOCIAL_PROFILE.name}`}
      >
        <NAVBAR_SOCIAL_PROFILE.Icon className="h-5 w-5" aria-hidden="true" />
      </a>
      <button type="button" className={`${ICON_BUTTON} ${pad}`} aria-label="Search">
        <FaSearch className="h-5 w-5" aria-hidden="true" />
      </button>
      <div className="relative">
        <button type="button" className={`relative ${ICON_BUTTON} ${pad}`} aria-label="Notifications">
          <BellIcon filled className="h-5 w-5" />
        </button>
      </div>
      {menu && (
        <button type="button" className={`${ICON_BUTTON} ${pad}`} aria-label="Open main menu">
          <span className="sr-only">Open main menu</span>
          <FaBars className="block h-5 w-5" aria-hidden="true" />
        </button>
      )}
    </>
  );
}
