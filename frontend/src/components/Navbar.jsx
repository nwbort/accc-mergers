import { Link, useLocation } from 'react-router';
import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import { FaSearch, FaChevronDown } from 'react-icons/fa';
import { FaHouse, FaListUl, FaScaleBalanced, FaNewspaper, FaEllipsis } from 'react-icons/fa6';
import { useTracking } from '../context/TrackingContext';
import NotificationPanel from './NotificationPanel';
import BellIcon from './BellIcon';
import { NAVBAR_SOCIAL_PROFILE } from '../constants/socialProfiles';
import { NAV_PAGES } from '../constants/navPages';
import MaterialShape from './MaterialShape';

const SCROLL_HIDE_THRESHOLD_PX = 50;

const navLinks = NAV_PAGES.filter((p) => p.inNavbar)
  .sort((a, b) => a.navOrder - b.navOrder)
  .map(({ path, label, navbarLabel, shortcut }) => ({ path, label: navbarLabel || label, shortcut }));

const mainNavLinks = navLinks.slice(0, 2);
const moreNavLinks = navLinks.slice(2);

// On a phone the navbar's links move to a bottom navigation bar, as the
// Android app's tabs do: these destinations get a slot each (in navbar order)
// and the rest go under "More". Four plus More is what fits at 360px.
const BOTTOM_BAR_ICONS = {
  '/': FaHouse,
  '/mergers': FaListUl,
  '/phase-2': FaScaleBalanced,
  '/digest': FaNewspaper,
};
const bottomBarLinks = navLinks.filter(({ path }) => BOTTOM_BAR_ICONS[path]);
const bottomMoreLinks = navLinks.filter(({ path }) => !BOTTOM_BAR_ICONS[path]);

// The height the bottom bar takes, published as --bottom-bar so the page can
// leave room for it (App.jsx pads the layout by it).
const BOTTOM_BAR_HEIGHT = '5rem';

// An M3 icon button: a 40px circle with a state layer on hover.
const ICON_BUTTON =
  'press-morph inline-flex items-center justify-center h-10 w-10 rounded-full text-gray-600 hover:text-gray-900 hover:bg-gray-900/[0.08] focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

// One desktop nav link. Full mode renders the whole of navLinks with it and
// condensed mode the first two, which is why it is a component rather than
// the same markup typed out under each branch.
function DesktopNavLink({ path, label, shortcut, active, showShortcutHint }) {
  return (
    <Link
      to={path}
      aria-current={active ? 'page' : undefined}
      className={`press-morph relative inline-flex items-center h-10 px-4 rounded-full text-sm ${
        active
          ? 'bg-secondary-container text-on-secondary-container font-semibold'
          : 'text-gray-600 font-medium hover:text-gray-900 hover:bg-gray-900/[0.08]'
      }`}
    >
      {label}
      {shortcut && showShortcutHint && (
        <span className="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 rounded-full bg-primary text-[10px] font-bold text-white animate-pop-in">
          {shortcut}
        </span>
      )}
    </Link>
  );
}

function Navbar({ onOpenSearch }) {
  const location = useLocation();
  const [isVisible, setIsVisible] = useState(true);
  const [lastScrollY, setLastScrollY] = useState(0);
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [notificationPanelOpen, setNotificationPanelOpen] = useState(false);
  const [showShortcutHints, setShowShortcutHints] = useState(false);
  const [navMode, setNavMode] = useState('full'); // 'full' | 'condensed' | 'mobile' | 'tiny'
  // Whether the hamburger layout has room for the social icon as well.
  const [mobileSocialFits, setMobileSocialFits] = useState(true);
  const containerRef = useRef(null);
  const probeFullRef = useRef(null);
  const probeCondensedRef = useRef(null);
  const probeMobileRef = useRef(null);
  const probeMobileSocialRef = useRef(null);
  const moreMenuRef = useRef(null);
  const moreButtonRef = useRef(null);
  const { unseenCount } = useTracking();

  useLayoutEffect(() => {
    const container = containerRef.current;
    const probeFull = probeFullRef.current;
    const probeCondensed = probeCondensedRef.current;
    const probeMobile = probeMobileRef.current;
    const probeMobileSocial = probeMobileSocialRef.current;
    if (!container || !probeFull || !probeCondensed || !probeMobile || !probeMobileSocial) return;
    const check = () => {
      const available = container.clientWidth;
      setMobileSocialFits(probeMobileSocial.offsetWidth <= available);
      if (probeFull.offsetWidth <= available) {
        setNavMode('full');
      } else if (probeCondensed.offsetWidth <= available) {
        setNavMode('condensed');
      } else if (probeMobile.offsetWidth <= available) {
        setNavMode('mobile');
      } else {
        setNavMode('tiny');
      }
    };
    check();
    const ro = new ResizeObserver(check);
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!moreOpen) return;
    const handleClick = (e) => {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target)) {
        setMoreOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [moreOpen]);

  // Escape closes the "More" menu and puts focus back on its trigger, so a
  // keyboard user isn't stranded inside an open dropdown.
  useEffect(() => {
    if (!moreOpen) return;
    const handleEscape = (e) => {
      if (e.key !== 'Escape') return;
      setMoreOpen(false);
      moreButtonRef.current?.focus();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [moreOpen]);

  // Reset menu state when navMode changes (recommended pattern over useEffect:
  // https://react.dev/reference/react/useState#storing-information-from-previous-renders)
  const [prevNavMode, setPrevNavMode] = useState(navMode);
  if (prevNavMode !== navMode) {
    setPrevNavMode(navMode);
    if (navMode !== 'mobile' && navMode !== 'tiny' && mobileMenuOpen) setMobileMenuOpen(false);
    if (navMode !== 'condensed' && moreOpen) setMoreOpen(false);
  }

  const isActive = (path) => location.pathname === path;
  const isHamburger = navMode === 'mobile' || navMode === 'tiny';
  const showSocial = navMode === 'full' || (isHamburger && mobileSocialFits);
  const isMoreActive = moreNavLinks.some(({ path }) => isActive(path));
  const isBottomMoreActive = bottomMoreLinks.some(({ path }) => isActive(path));
  const mobileMenuRef = useRef(null);
  const mobileMoreButtonRef = useRef(null);

  // Leave room under the page for the bottom bar while it shows.
  useEffect(() => {
    const root = document.documentElement;
    if (isHamburger) root.style.setProperty('--bottom-bar', BOTTOM_BAR_HEIGHT);
    else root.style.removeProperty('--bottom-bar');
    return () => root.style.removeProperty('--bottom-bar');
  }, [isHamburger]);

  // The "More" sheet closes on Escape (focus back to its button) and on a
  // press anywhere outside it.
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const handleEscape = (e) => {
      if (e.key !== 'Escape') return;
      setMobileMenuOpen(false);
      mobileMoreButtonRef.current?.focus();
    };
    const handleClick = (e) => {
      if (mobileMenuRef.current?.contains(e.target)) return;
      if (mobileMoreButtonRef.current?.contains(e.target)) return;
      setMobileMenuOpen(false);
    };
    document.addEventListener('keydown', handleEscape);
    document.addEventListener('mousedown', handleClick);
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [mobileMenuOpen]);

  // A route change closes the sheet.
  const [prevPath, setPrevPath] = useState(location.pathname);
  if (prevPath !== location.pathname) {
    setPrevPath(location.pathname);
    if (mobileMenuOpen) setMobileMenuOpen(false);
  }

  // Show shortcut hint badges while "g" is held/pending
  useEffect(() => {
    let timer = null;
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT' || e.target.isContentEditable) return;
      if (e.key === 'g' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        setShowShortcutHints(true);
        clearTimeout(timer);
        timer = setTimeout(() => setShowShortcutHints(false), 2000);
      }
    };
    const handleKeyUp = (e) => {
      if (showShortcutHints && e.key !== 'g') {
        setShowShortcutHints(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      clearTimeout(timer);
    };
  }, [showShortcutHints]);

  useEffect(() => {
    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      setIsScrolled(currentScrollY > 10);
      if (currentScrollY < lastScrollY) {
        setIsVisible(true);
      } else if (currentScrollY > lastScrollY && currentScrollY > SCROLL_HIDE_THRESHOLD_PX) {
        setIsVisible(false);
      }
      setLastScrollY(currentScrollY);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [lastScrollY]);

  return (
    <>
    <nav
      aria-label="Main"
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isVisible ? 'translate-y-0' : '-translate-y-full'
      } ${
        // M3's top app bar: the page's own tone at rest, lifting to a
        // container tone (not a shadow) once content scrolls under it.
        isScrolled ? 'bg-surface-container' : 'bg-surface'
      }`}
    >
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-primary focus:text-white focus:px-4 focus:py-2 focus:rounded-full"
      >
        Skip to main content
      </a>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div ref={containerRef} className="flex justify-between h-16 relative">

          {/* Full probe: all links + social icon + search + bell */}
          <div
            ref={probeFullRef}
            aria-hidden="true"
            className="absolute top-0 left-0 invisible pointer-events-none flex items-center h-16 whitespace-nowrap"
          >
            <span className="w-8 h-8 mr-2.5" />
            <span className="text-lg font-bold tracking-tight">australian merger tracker</span>
            <div className="ml-8 flex gap-1">
              {navLinks.map(({ label }) => (
                <span key={label} className="px-4 text-sm font-semibold">{label}</span>
              ))}
            </div>
            <div className="ml-2 flex items-center gap-1">
              <div className="w-10 h-10" />
              <div className="w-10 h-10" />
              <div className="w-10 h-10" />
            </div>
          </div>

          {/* Condensed probe: Dashboard + Mergers + More + search + bell */}
          <div
            ref={probeCondensedRef}
            aria-hidden="true"
            className="absolute top-0 left-0 invisible pointer-events-none flex items-center h-16 whitespace-nowrap"
          >
            <span className="w-8 h-8 mr-2.5" />
            <span className="text-lg font-bold tracking-tight">australian merger tracker</span>
            <div className="ml-8 flex gap-1">
              <span className="px-4 text-sm font-semibold">Dashboard</span>
              <span className="px-4 text-sm font-semibold">Mergers</span>
              <span className="px-4 text-sm font-semibold">More ▾</span>
            </div>
            <div className="ml-2 flex items-center gap-1">
              <div className="w-10 h-10" />
              <div className="w-10 h-10" />
            </div>
          </div>

          {/* Mobile probe: brand + search + bell (the links are in the
              bottom bar) */}
          <div
            ref={probeMobileRef}
            aria-hidden="true"
            className="absolute top-0 left-0 invisible pointer-events-none flex items-center h-16 whitespace-nowrap"
          >
            <span className="w-8 h-8 mr-2.5" />
            <span className="text-lg font-bold tracking-tight">australian merger tracker</span>
            <div className="ml-2 flex items-center">
              <div className="w-10 h-10" />
              <div className="w-10 h-10" />
            </div>
          </div>

          {/* Mobile + social probe: brand + social icon + search + bell */}
          <div
            ref={probeMobileSocialRef}
            aria-hidden="true"
            className="absolute top-0 left-0 invisible pointer-events-none flex items-center h-16 whitespace-nowrap"
          >
            <span className="w-8 h-8 mr-2.5" />
            <span className="text-lg font-bold tracking-tight">australian merger tracker</span>
            <div className="ml-2 flex items-center">
              <div className="w-10 h-10" />
              <div className="w-10 h-10" />
              <div className="w-10 h-10" />
            </div>
          </div>

          {/* Left: brand + nav links */}
          <div className="flex items-center min-w-0">
            <Link to="/" className="flex items-center gap-2.5 group rounded-full min-w-0">
              {/* The brand mark: the app's nine-sided cookie, turning a
                  little on hover. */}
              <MaterialShape
                shape="cookie9"
                className={`flex-shrink-0 w-8 h-8 text-primary transition-transform duration-500 ease-spring group-hover:rotate-45 ${
                  navMode === 'tiny' ? 'hidden' : ''
                }`}
              >
                <path d="M30 64V38l20 18 20-18v26" fill="none" stroke="white" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
              </MaterialShape>
              <span className="text-lg font-bold text-primary tracking-tight truncate">
                australian merger tracker
              </span>
            </Link>

            {/* Full mode: all links */}
            {navMode === 'full' && (
              <div className="ml-8 flex gap-1">
                {navLinks.map(({ path, label, shortcut }) => (
                  <DesktopNavLink
                    key={path}
                    path={path}
                    label={label}
                    shortcut={shortcut}
                    active={isActive(path)}
                    showShortcutHint={showShortcutHints}
                  />
                ))}
              </div>
            )}

            {/* Condensed mode: Dashboard + Mergers + More dropdown */}
            {navMode === 'condensed' && (
              <div className="ml-8 flex items-center gap-1">
                {mainNavLinks.map(({ path, label, shortcut }) => (
                  <DesktopNavLink
                    key={path}
                    path={path}
                    label={label}
                    shortcut={shortcut}
                    active={isActive(path)}
                    showShortcutHint={showShortcutHints}
                  />
                ))}
                <div ref={moreMenuRef} className="relative">
                  <button
                    ref={moreButtonRef}
                    onClick={() => setMoreOpen(!moreOpen)}
                    className={`press-morph inline-flex items-center gap-1.5 h-10 px-4 rounded-full text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
                      isMoreActive || moreOpen
                        ? 'bg-secondary-container text-on-secondary-container font-semibold'
                        : 'text-gray-600 font-medium hover:text-gray-900 hover:bg-gray-900/[0.08]'
                    }`}
                    aria-expanded={moreOpen}
                    aria-haspopup="true"
                  >
                    More
                    <FaChevronDown
                      className={`h-3 w-3 transition-transform duration-300 ease-spring ${moreOpen ? 'rotate-180' : ''}`}
                      aria-hidden="true"
                    />
                  </button>
                  {moreOpen && (
                    <div className="absolute top-full left-0 mt-2 w-52 bg-surface-container shadow-elevated rounded-2xl p-2 z-50 animate-pop-in origin-top-left">
                      {moreNavLinks.map(({ path, label }) => (
                        <Link
                          key={path}
                          to={path}
                          aria-current={isActive(path) ? 'page' : undefined}
                          className={`block px-4 py-2.5 rounded-xl text-sm ${
                            isActive(path)
                              ? 'bg-secondary-container text-on-secondary-container font-semibold'
                              : 'text-gray-700 font-medium hover:bg-gray-900/[0.08] hover:text-gray-900'
                          }`}
                          onClick={() => setMoreOpen(false)}
                        >
                          {label}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Right: social icon, search, bell. The social icon
              (constants/socialProfiles.js) is left out of the condensed
              layout, where the row is tightest, and out of the phone layout
              when it doesn't fit. */}
          <div className="flex items-center gap-0.5 flex-shrink-0">
            {showSocial && (
              <a
                href={NAVBAR_SOCIAL_PROFILE.href}
                target="_blank"
                rel="noopener noreferrer me"
                className={`${ICON_BUTTON} ${NAVBAR_SOCIAL_PROFILE.hoverClass}`}
                aria-label={`mergers.fyi on ${NAVBAR_SOCIAL_PROFILE.name} (opens in a new tab)`}
                title={`Follow on ${NAVBAR_SOCIAL_PROFILE.name}`}
              >
                <NAVBAR_SOCIAL_PROFILE.Icon className="h-5 w-5" aria-hidden="true" />
              </a>
            )}
            <button
              onClick={onOpenSearch}
              className={ICON_BUTTON}
              aria-label="Search"
            >
              <FaSearch className="h-[18px] w-[18px]" aria-hidden="true" />
            </button>
            <div className="relative">
              <button
                onMouseDown={(e) => e.stopPropagation()}
                onClick={() => setNotificationPanelOpen(!notificationPanelOpen)}
                className={`relative ${ICON_BUTTON} ${notificationPanelOpen ? 'bg-secondary-container text-on-secondary-container' : ''}`}
                aria-expanded={notificationPanelOpen}
                aria-label={`Notifications${unseenCount > 0 ? `, ${unseenCount} new` : ''}`}
              >
                <BellIcon filled className="h-5 w-5" />
                {unseenCount > 0 && (
                  // M3's large badge: the error colour, a pill that grows
                  // with its count.
                  <span className="absolute top-1 right-0.5 flex h-4 min-w-4 items-center justify-center">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-600 opacity-30"></span>
                    <span className="relative inline-flex h-4 min-w-4 px-1 items-center justify-center rounded-full bg-[#b3261e] text-[10px] font-bold text-white">
                      {unseenCount > 9 ? '9+' : unseenCount}
                    </span>
                  </span>
                )}
              </button>
              <NotificationPanel
                isOpen={notificationPanelOpen}
                onClose={() => setNotificationPanelOpen(false)}
              />
            </div>
          </div>
        </div>
      </div>
    </nav>

    {/* Phone: the app's bottom navigation bar. Each destination is an icon
        over its label, the active one in M3's pill indicator. */}
    {isHamburger && (
      <nav
        aria-label="Mobile navigation"
        className="fixed bottom-0 left-0 right-0 z-50 bg-surface-container"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        {mobileMenuOpen && (
          <div
            ref={mobileMenuRef}
            id="mobile-menu"
            className="absolute bottom-full left-0 right-0 bg-surface-container-low rounded-t-3xl shadow-elevated px-3 pt-2 pb-3 animate-slide-up"
          >
            <div className="mx-auto mb-2 h-1 w-8 rounded-full bg-outline-variant" aria-hidden="true" />
            <ul className="space-y-1">
              {bottomMoreLinks.map(({ path, label }) => (
                <li key={path}>
                  <Link
                    to={path}
                    aria-current={isActive(path) ? 'page' : undefined}
                    className={`flex items-center h-14 px-5 rounded-full text-base ${
                      isActive(path)
                        ? 'bg-secondary-container text-on-secondary-container font-semibold'
                        : 'text-gray-700 font-medium hover:bg-gray-900/[0.08]'
                    }`}
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
        <ul className="flex h-20 items-stretch justify-around px-1">
          {bottomBarLinks.map(({ path, label }) => {
            const Icon = BOTTOM_BAR_ICONS[path];
            const active = isActive(path);
            return (
              <li key={path} className="flex-1 min-w-0">
                <Link
                  to={path}
                  aria-current={active ? 'page' : undefined}
                  className="group flex h-full flex-col items-center justify-center gap-1 rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <span
                    className={`flex h-8 w-14 items-center justify-center rounded-full transition-all duration-300 ease-spring ${
                      active
                        ? 'bg-secondary-container text-on-secondary-container'
                        : 'text-gray-600 group-hover:bg-gray-900/[0.08]'
                    }`}
                  >
                    <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
                  </span>
                  <span className={`text-[11px] sm:text-xs whitespace-nowrap ${active ? 'font-bold text-gray-900' : 'font-medium text-gray-600'}`}>
                    {label}
                  </span>
                </Link>
              </li>
            );
          })}
          <li className="flex-1 min-w-0">
            <button
              ref={mobileMoreButtonRef}
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-menu"
              aria-label={mobileMenuOpen ? 'Close main menu' : 'Open main menu'}
              className="group flex h-full w-full flex-col items-center justify-center gap-1 rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <span
                className={`flex h-8 w-14 items-center justify-center rounded-full transition-all duration-300 ease-spring ${
                  mobileMenuOpen || isBottomMoreActive
                    ? 'bg-secondary-container text-on-secondary-container'
                    : 'text-gray-600 group-hover:bg-gray-900/[0.08]'
                }`}
              >
                <FaEllipsis className="h-[18px] w-[18px]" aria-hidden="true" />
              </span>
              <span className={`text-[11px] sm:text-xs ${mobileMenuOpen || isBottomMoreActive ? 'font-bold text-gray-900' : 'font-medium text-gray-600'}`} aria-hidden="true">
                More
              </span>
            </button>
          </li>
        </ul>
      </nav>
    )}
    </>
  );
}

export default Navbar;
