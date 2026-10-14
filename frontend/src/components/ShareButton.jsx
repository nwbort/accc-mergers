import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { FaShareNodes, FaLink, FaCheck, FaLinkedin, FaBluesky, FaEnvelope } from 'react-icons/fa6';
import { HEADER_BUTTON_BASE, HEADER_BUTTON_VARIANTS } from '../constants/headerButton';
import { prefersNativeShare, shareTargets, shareUrl } from '../utils/share';

const TARGET_ICONS = {
  linkedin: FaLinkedin,
  bluesky: FaBluesky,
  email: FaEnvelope,
};

const MENU_WIDTH = 256; // w-64

const ITEM_CLASS =
  'flex w-full items-center gap-2.5 px-3 py-2 text-sm text-gray-700 rounded-lg hover:bg-gray-100 focus:outline-none focus-visible:bg-gray-100 focus-visible:ring-2 focus-visible:ring-primary';

/**
 * "Share" pill that sits beside TrackButton in a page header.
 *
 * On a phone it opens the device's share sheet. Everywhere else it opens a
 * small menu: copy the link, or share it to LinkedIn, Bluesky or email.
 *
 * The menu is portalled to <body> because the headers it sits in clip their
 * overflow (the merger detail card's `.card-accent` does), which would cut a
 * dropdown off at the card's edge. Focus moves into the menu when it opens and
 * back to the button when it closes, so the portal doesn't strand keyboard
 * users at the end of the document.
 *
 * @param {string} path  Site path to share; made absolute against SITE_URL.
 * @param {string} title What the link is — the post text / email subject.
 */
function ShareButton({ path, title, onDark = false }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [position, setPosition] = useState(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const menuId = useId();
  const variant = onDark ? HEADER_BUTTON_VARIANTS.dark : HEADER_BUTTON_VARIANTS.light;
  const url = shareUrl(path);

  const close = useCallback((restoreFocus = true) => {
    setOpen(false);
    setCopied(false);
    setPosition(null);
    if (restoreFocus) buttonRef.current?.focus();
  }, []);

  // Anchor the menu under the button's right edge, in document coordinates so
  // it scrolls with the page; clamped so it never runs off the left edge.
  const place = useCallback(() => {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (!rect) return;
    setPosition({
      top: rect.bottom + window.scrollY + 8,
      left: Math.max(8, rect.right + window.scrollX - MENU_WIDTH),
    });
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    window.addEventListener('resize', place);
    return () => window.removeEventListener('resize', place);
  }, [open, place]);

  const shown = open && position !== null;

  useEffect(() => {
    if (shown) menuRef.current?.querySelector('button, a')?.focus();
  }, [shown]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (e) => {
      if (menuRef.current?.contains(e.target) || buttonRef.current?.contains(e.target)) return;
      close(false);
    };
    const onKeyDown = (e) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open, close]);

  const handleClick = async () => {
    if (open) {
      close();
      return;
    }
    if (prefersNativeShare()) {
      try {
        await navigator.share({ title, url });
        return;
      } catch (err) {
        // The reader dismissed the sheet: that is an answer, not a failure.
        if (err?.name === 'AbortError') return;
        // Anything else (no user activation, a blocked target) falls through
        // to the menu so there is still a way to get the link.
      }
    }
    place();
    setOpen(true);
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      // No clipboard access (insecure context, permission denied): select
      // the visible link instead so the reader can copy it by hand.
      const field = menuRef.current?.querySelector('input');
      field?.focus();
      field?.select();
    }
  };

  // Leaving the menu by Tab closes it; the next element in the page's own
  // order is the reader's to choose, so focus is not pulled back.
  const handleBlur = (e) => {
    const next = e.relatedTarget;
    // Moving to the Share button itself is left to its click, which toggles
    // the menu shut; closing here too would have that click reopen it.
    if (menuRef.current?.contains(next) || buttonRef.current?.contains(next)) return;
    close(false);
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={handleClick}
        className={`${HEADER_BUTTON_BASE} ${open ? variant.active : variant.inactive} ${variant.focus || ''}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label="Share this page"
      >
        <FaShareNodes className="w-3.5 h-3.5" aria-hidden="true" />
        Share
      </button>
      {shown && createPortal(
        <div
          ref={menuRef}
          id={menuId}
          role="dialog"
          aria-label="Share this page"
          onBlur={handleBlur}
          className="absolute z-50 w-64 p-2 bg-white rounded-xl border border-gray-200 shadow-lg animate-fade-in"
          style={{ top: position.top, left: position.left }}
        >
          <button type="button" onClick={copyLink} className={ITEM_CLASS}>
            {copied
              ? <FaCheck className="w-4 h-4 text-emerald-600" aria-hidden="true" />
              : <FaLink className="w-4 h-4 text-gray-500" aria-hidden="true" />}
            {copied ? 'Link copied' : 'Copy link'}
          </button>
          <input
            type="text"
            readOnly
            value={url}
            aria-label="Link to this page"
            onFocus={(e) => e.target.select()}
            className="mt-1 mb-2 w-full px-2 py-1 text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          <div className="border-t border-gray-100 pt-1">
            {shareTargets({ url, title }).map(({ id, label, href }) => {
              const Icon = TARGET_ICONS[id];
              const external = !href.startsWith('mailto:');
              return (
                <a
                  key={id}
                  href={href}
                  className={ITEM_CLASS}
                  onClick={() => close(false)}
                  {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                >
                  <Icon className="w-4 h-4 text-gray-500" aria-hidden="true" />
                  {label}
                  {external && <span className="sr-only"> (opens in a new tab)</span>}
                </a>
              );
            })}
          </div>
          <p className="sr-only" aria-live="polite">{copied ? 'Link copied to clipboard' : ''}</p>
        </div>,
        document.body,
      )}
    </>
  );
}

export default ShareButton;
