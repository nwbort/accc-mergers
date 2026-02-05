import { Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { useTracking } from '../context/TrackingContext';
import NotificationPanel from './NotificationPanel';

const SCROLL_HIDE_THRESHOLD_PX = 50;

function Navbar() {
  const location = useLocation();
  const [isVisible, setIsVisible] = useState(true);
  const [lastScrollY, setLastScrollY] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notificationPanelOpen, setNotificationPanelOpen] = useState(false);
  const { unseenCount, trackedMergerIds } = useTracking();

  const isActive = (path) => {
    return location.pathname === path;
  };

  useEffect(() => {
    const handleScroll = () => {
      const currentScrollY = window.scrollY;

      // Show navbar when scrolling up, hide when scrolling down
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
      className={`fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-200 transition-transform duration-300 ${
        isVisible ? 'translate-y-0' : '-translate-y-full'
      }`}
    >
      {/* Skip to main content link for keyboard navigation */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-primary focus:text-white focus:px-4 focus:py-2 focus:rounded"
      >
        Skip to main content
      </a>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <Link to="/" className="flex items-center">
              <span className="text-xl font-bold text-primary">
                Australian merger tracker
              </span>
            </Link>
            <div className="hidden sm:ml-8 sm:flex sm:space-x-8">
              <Link
                to="/"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  isActive('/')
                    ? 'border-primary text-gray-900'
                    : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                }`}
              >
                Dashboard
              </Link>
              <Link
                to="/mergers"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  isActive('/mergers')
                    ? 'border-primary text-gray-900'
                    : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                }`}
              >
                Mergers
              </Link>
              <Link
                to="/timeline"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  isActive('/timeline')
                    ? 'border-primary text-gray-900'
                    : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                }`}
              >
                Timeline
              </Link>
              <Link
                to="/industries"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  isActive('/industries')
                    ? 'border-primary text-gray-900'
                    : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                }`}
              >
                Industries
              </Link>
              <Link
                to="/commentary"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  isActive('/commentary')
                    ? 'border-primary text-gray-900'
                    : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                }`}
              >
                Commentary
              </Link>
            </div>
          </div>
          {/* Right side: Notifications bell + mobile menu */}
          <div className="flex items-center gap-2">
            {/* Notifications bell */}
            <div className="relative">
              <button
                onClick={() => setNotificationPanelOpen(!notificationPanelOpen)}
                className="relative inline-flex items-center justify-center p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary"
                aria-expanded={notificationPanelOpen}
                aria-label={`Notifications${unseenCount > 0 ? `, ${unseenCount} new` : ''}`}
              >
                <svg
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth="1.5"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
                  />
                </svg>
                {unseenCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-white transform bg-red-500 rounded-full min-w-[1.25rem]">
                    {unseenCount > 99 ? '99+' : unseenCount}
                  </span>
                )}
                {unseenCount === 0 && trackedMergerIds.length > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 inline-flex items-center justify-center w-2.5 h-2.5 bg-primary rounded-full" />
                )}
              </button>
              <NotificationPanel
                isOpen={notificationPanelOpen}
                onClose={() => setNotificationPanelOpen(false)}
              />
            </div>
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="sm:hidden inline-flex items-center justify-center p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary"
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-menu"
              aria-label={mobileMenuOpen ? "Close main menu" : "Open main menu"}
            >
              <span className="sr-only">{mobileMenuOpen ? "Close" : "Open"} main menu</span>
              {mobileMenuOpen ? (
                <svg
                  className="block h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth="1.5"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              ) : (
                <svg
                  className="block h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth="1.5"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div id="mobile-menu" className="sm:hidden">
          <nav aria-label="Mobile navigation" className="pt-2 pb-3 space-y-1">
            <Link
              to="/"
              className={`block pl-3 pr-4 py-2 border-l-4 text-base font-medium ${
                isActive('/')
                  ? 'bg-primary-light border-primary text-white'
                  : 'border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-900'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Dashboard
            </Link>
            <Link
              to="/mergers"
              className={`block pl-3 pr-4 py-2 border-l-4 text-base font-medium ${
                isActive('/mergers')
                  ? 'bg-primary-light border-primary text-white'
                  : 'border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-900'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Mergers
            </Link>
            <Link
              to="/timeline"
              className={`block pl-3 pr-4 py-2 border-l-4 text-base font-medium ${
                isActive('/timeline')
                  ? 'bg-primary-light border-primary text-white'
                  : 'border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-900'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Timeline
            </Link>
            <Link
              to="/industries"
              className={`block pl-3 pr-4 py-2 border-l-4 text-base font-medium ${
                isActive('/industries')
                  ? 'bg-primary-light border-primary text-white'
                  : 'border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-900'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Industries
            </Link>
            <Link
              to="/commentary"
              className={`block pl-3 pr-4 py-2 border-l-4 text-base font-medium ${
                isActive('/commentary')
                  ? 'bg-primary-light border-primary text-white'
                  : 'border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-900'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Commentary
            </Link>
          </nav>
        </div>
      )}
    </nav>
  );
}

export default Navbar;
