import { useState, useRef, useId, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { GLOSSARY_BY_ID } from '../constants/glossary';

const TOOLTIP_WIDTH = 288; // px — matches w-72
const VIEWPORT_MARGIN = 8; // px gap from the viewport edge
const GAP = 8; // px gap between the trigger and the popover
const CLOSE_DELAY_MS = 120; // grace period so the pointer can travel into the popover

/**
 * Inline term that reveals its glossary definition on hover, focus or tap.
 *
 * The definition shown is exactly the one stored in constants/glossary.js, so
 * it always matches the corresponding entry on the Glossary page. The popover
 * also links through to /glossary#<id> for the full context.
 *
 * Usage: <GlossaryTerm id="phase-1">Phase 1</GlossaryTerm>
 * Children are optional — when omitted the canonical term name is shown.
 */
export default function GlossaryTerm({ id, children, className = '' }) {
  const entry = GLOSSARY_BY_ID[id];
  const triggerRef = useRef(null);
  const closeTimer = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState(null); // { top, left, placement }
  const tooltipId = useId();

  const computePosition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const width = Math.min(TOOLTIP_WIDTH, window.innerWidth - VIEWPORT_MARGIN * 2);

    // Prefer below; flip above when there isn't room and there's more space up top.
    const spaceBelow = window.innerHeight - rect.bottom;
    const placement = spaceBelow < 160 && rect.top > spaceBelow ? 'top' : 'bottom';

    let left = rect.left + rect.width / 2 - width / 2;
    left = Math.max(VIEWPORT_MARGIN, Math.min(left, window.innerWidth - width - VIEWPORT_MARGIN));

    const top = placement === 'bottom' ? rect.bottom + GAP : rect.top - GAP;
    setCoords({ top, left, width, placement });
  }, []);

  const cancelClose = useCallback(() => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }, []);

  const show = useCallback(() => {
    cancelClose();
    computePosition();
    setOpen(true);
  }, [cancelClose, computePosition]);

  const hide = useCallback(() => setOpen(false), []);

  const scheduleClose = useCallback(() => {
    cancelClose();
    closeTimer.current = setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  }, [cancelClose]);

  // While open, dismiss on Escape and recompute/close when the layout shifts.
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    const onReflow = () => setOpen(false);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('scroll', onReflow, true);
    window.addEventListener('resize', onReflow);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', onReflow, true);
      window.removeEventListener('resize', onReflow);
    };
  }, [open]);

  useEffect(() => cancelClose, [cancelClose]);

  // Unknown id: fail gracefully by rendering plain text (and warn in dev).
  if (!entry) {
    if (import.meta.env?.DEV) {
      console.warn(`GlossaryTerm: no glossary entry for id "${id}"`);
    }
    return <>{children}</>;
  }

  const label = children ?? entry.term;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-describedby={open ? tooltipId : undefined}
        onMouseEnter={show}
        onMouseLeave={scheduleClose}
        onFocus={show}
        onBlur={hide}
        onClick={() => (open ? hide() : show())}
        className={`inline cursor-help border-b border-dotted border-primary/50 text-inherit underline-offset-2 transition-colors hover:border-primary hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:rounded ${className}`}
      >
        {label}
      </button>

      {open && coords && createPortal(
        <div
          id={tooltipId}
          role="tooltip"
          onMouseEnter={cancelClose}
          onMouseLeave={scheduleClose}
          style={{
            position: 'fixed',
            top: coords.placement === 'bottom' ? coords.top : undefined,
            bottom: coords.placement === 'top' ? window.innerHeight - coords.top : undefined,
            left: coords.left,
            width: coords.width,
          }}
          className="z-[60] animate-fade-in rounded-xl border border-gray-200/80 bg-white p-3.5 text-left shadow-elevated"
        >
          <p className="text-sm font-semibold text-gray-900">
            {entry.term}
            {entry.abbr && entry.abbr !== entry.term && (
              <span className="ml-1.5 font-normal text-gray-400">({entry.abbr})</span>
            )}
          </p>
          <p className="mt-1 text-[13px] leading-relaxed text-gray-600">{entry.definition}</p>
          <Link
            to={`/glossary#${entry.id}`}
            onClick={hide}
            className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary transition-colors hover:text-primary-dark"
          >
            More in the glossary
            <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>,
        document.body
      )}
    </>
  );
}
