import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import { FaSearch, FaBars, FaTimes } from 'react-icons/fa';
import { useTracking } from '../context/TrackingContext';
import NotificationPanel from './NotificationPanel';
import BellIcon from './BellIcon';

const SCROLL_HIDE_THRESHOLD_PX = 50;

const navLinks = [
  { path: '/', label: 'Dashboard', shortcut: 'd' },
  { path: '/mergers', label: 'Mergers', shortcut: 'm' },
  { path: '/timeline', label: 'Timeline', shortcut: 't' },
  { path: '/industries', label: 'Industries', shortcut: 'i' },
  { path: '/commentary', label: 'Commentary', shortcut: 'c' },
  { path: '/analysis', label: 'Analysis', shortcut: 'a' },
  { path: '/digest', label: 'Catch me up' },
];

function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [isVisible, setIsVisible] = useState(true);
  const [lastScrollY, setLastScrollY] = useState(0);
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notificationPanelOpen, setNotificationPanelOpen] = useState(false);
  const [showShortcutHints, setShowShortcutHints] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchInputRef = useRef(null);
  const mobileSearchInputRef = useRef(null);
  const focusMobileSearchRef = useRef(false);
  const { unseenCount } = useTracking();

  const submitSearch = (query) => {
    const trimmed = query.trim();
    if (trimmed) {
      navigate(`/mergers?q=${encodeURIComponent(trimmed)}`);
    }
    setSearchOpen(false);
    setSearchQuery('');
  };

  const handleSearchKeyDown = (e) => {
    if (e.key === 'Enter') {
      submitSearch(searchQuery);
    } else if (e.key === 'Escape') {
      setSearchOpen(false);
      setSearchQuery('');
    }
  };

  const handleSearchIconClick = () => {
    if (searchOpen && searchQuery.trim()) {
      submitSearch(searchQuery);
    } else {
      setSearchOpen((prev) => !prev);
    }
  };

  useEffect(() => {
    if (searchOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [searchOpen]);

  useEffect(() => {
    const handleFocusNavbarSearch = () => {
      if (window.matchMedia('(min-width: 640px)').matches) {
        setSearchOpen(true);
        if (searchInputRef.current) {
          searchInputRef.current.focus();
        }
      } else {
        focusMobileSearchRef.current = true;
        setMobileMenuOpen(true);
      }
    };
    window.addEventListener('focus-navbar-search', handleFocusNavbarSearch);
    return () => window.removeEventListener('focus-navbar-search', handleFocusNavbarSearch);
  }, []);

  useEffect(() => {
    if (mobileMenuOpen && focusMobileSearchRef.current && mobileSearchInputRef.current) {
      mobileSearchInputRef.current.focus();
      focusMobileSearchRef.current = false;
    }
  }, [mobileMenuOpen]);

  const isActive = (path) => {
    return location.pathname === path;
  };

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
      // Hide on any key after g (the navigation will have happened)
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
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isVisible ? 'translate-y-0' : '-translate-y-full'
      } ${
        isScrolled
          ? 'bg-white/80 backdrop-blur-lg shadow-glass border-b border-gray-200/50'
          : 'bg-white border-b border-gray-100'
      }`}
    >
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-primary focus:text-white focus:px-4 focus:py-2 focus:rounded-lg"
      >
        Skip to main content
      </a>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to="/" className="flex items-center gap-2.5 group">
              <span className="text-lg font-bold text-primary tracking-tight">
                australian merger tracker
              </span>
            </Link>
            <div className="hidden sm:ml-10 sm:flex sm:space-x-1">
              {navLinks.map(({ path, label, shortcut }) => (
                <Link
                  key={path}
                  to={path}
                  className={`relative inline-flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                    isActive(path)
                      ? 'bg-primary/10 text-primary'
                      : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100/80'
                  }`}
                >
                  {label}
                  {shortcut && showShortcutHints && (
                    <span className="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 rounded bg-primary text-[10px] font-bold text-white shadow-sm animate-fade-in">
                      {shortcut}
                    </span>
                  )}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <div className="hidden sm:flex items-center">
              <div className={`flex items-center transition-all duration-200 ${searchOpen ? 'w-52' : 'w-8'}`}>
                {searchOpen && (
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={handleSearchKeyDown}
                    onBlur={() => { if (!searchQuery.trim()) { setSearchOpen(false); } }}
                    placeholder="Search mergers…"
                    className="w-full text-sm bg-gray-100/80 border border-gray-200 rounded-l-lg px-3 py-1.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/40"
                    aria-label="Search mergers"
                  />
                )}
                <button
                  onClick={handleSearchIconClick}
                  className={`inline-flex items-center justify-center p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100/80 transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${searchOpen ? 'rounded-r-lg border border-l-0 border-gray-200 bg-gray-100/80 hover:bg-gray-200/80' : 'rounded-lg'}`}
                  aria-label="Search"
                >
                  <FaSearch className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </div>
            <button
              onClick={() => { focusMobileSearchRef.current = true; setMobileMenuOpen(true); }}
              className="sm:hidden inline-flex items-center justify-center p-2 rounded-lg text-gray-500 hover:text-gray-900 hover:bg-gray-100/80 transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
              aria-label="Search"
            >
              <FaSearch className="h-5 w-5" aria-hidden="true" />
            </button>
            <div className="relative">
              <button
                onMouseDown={(e) => e.stopPropagation()}
                onClick={() => setNotificationPanelOpen(!notificationPanelOpen)}
                className="relative inline-flex items-center justify-center p-2 rounded-lg text-gray-500 hover:text-gray-900 hover:bg-gray-100/80 transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
                aria-expanded={notificationPanelOpen}
                aria-label={`Notifications${unseenCount > 0 ? `, ${unseenCount} new` : ''}`}
              >
                <BellIcon className="h-5 w-5" />
                {unseenCount > 0 && (
                  <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-40"></span>
                    <span className="relative inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-accent text-[10px] font-bold text-white">
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
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="sm:hidden inline-flex items-center justify-center p-2 rounded-lg text-gray-500 hover:text-gray-900 hover:bg-gray-100/80 transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-menu"
              aria-label={mobileMenuOpen ? "Close main menu" : "Open main menu"}
            >
              <span className="sr-only">{mobileMenuOpen ? "Close" : "Open"} main menu</span>
              {mobileMenuOpen ? (
                <FaTimes className="block h-5 w-5" aria-hidden="true" />
              ) : (
                <FaBars className="block h-5 w-5" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
      </div>

      {mobileMenuOpen && (
        <div id="mobile-menu" className="sm:hidden border-t border-gray-100 bg-white/95 backdrop-blur-lg">
          <div className="px-3 pt-3 pb-1">
            <div className="flex items-center gap-2 bg-gray-100/80 border border-gray-200 rounded-lg px-3 py-2">
              <FaSearch className="h-4 w-4 text-gray-400 shrink-0" aria-hidden="true" />
              <input
                ref={mobileSearchInputRef}
                type="text"
                placeholder="Search mergers…"
                className="flex-1 text-sm bg-transparent text-gray-900 placeholder-gray-400 focus:outline-none"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.target.value.trim()) {
                    navigate(`/mergers?q=${encodeURIComponent(e.target.value.trim())}`);
                    setMobileMenuOpen(false);
                  }
                }}
                aria-label="Search mergers"
              />
            </div>
          </div>
          <nav aria-label="Mobile navigation" className="px-3 py-3 space-y-1">
            {navLinks.map(({ path, label }) => (
              <Link
                key={path}
                to={path}
                className={`block px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive(path)
                    ? 'bg-primary/10 text-primary'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`}
                onClick={() => setMobileMenuOpen(false)}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </nav>
  );
}

export default Navbar;
