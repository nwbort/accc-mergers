import { useCallback, useEffect, useRef, useState } from 'react';
import { getBusinessDayProgress } from '../utils/businessDayProgress';
import { useFetchData } from '../hooks/useFetchData';
import { API_ENDPOINTS } from '../config';
import { MERGER_STATUS, PHASES } from '../constants/mergerStatus';

// How long the badge must be pressed before the hidden estimate appears.
const LONG_PRESS_MS = 450;

/**
 * A quiet, undocumented flourish over the "Under assessment" tag: press and
 * hold it (touch or mouse) on a Phase 1 matter that is still under assessment
 * and it reveals that matter's estimated chance of being referred to Phase 2.
 *
 * The estimate reads referral-probability-by-day.json — a survival-style curve
 * giving P(referred to Phase 2 | still undecided at business day N) — and
 * indexes it by how many business days this matter has been running. The longer
 * a live review sits undecided, the more the quick clearances have dropped out
 * of the comparison pool, so the odds ratchet up.
 *
 * When the matter isn't an eligible Phase 1 assessment (waiver, Phase 2, already
 * decided, or missing dates) the wrapper is inert and simply renders its child
 * badge untouched.
 */
function Phase2OddsReveal({ merger, children }) {
  const progress = getBusinessDayProgress(merger);
  const eligible =
    !!progress &&
    merger?.status === MERGER_STATUS.UNDER_ASSESSMENT &&
    !!merger?.stage &&
    merger.stage.includes(PHASES.PHASE_1);

  // Only fetch the curve when the badge could actually reveal it — a falsy URL
  // pauses useFetchData, so ineligible matters make no network request.
  const { data } = useFetchData(
    eligible ? API_ENDPOINTS.referralProbabilityByDay : null,
    { cacheKey: 'referral-probability-by-day' }
  );

  const [revealed, setRevealed] = useState(false);
  const timerRef = useRef(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startPress = useCallback(() => {
    clearTimer();
    timerRef.current = setTimeout(() => setRevealed(true), LONG_PRESS_MS);
  }, [clearTimer]);

  const endPress = useCallback(() => {
    clearTimer();
    setRevealed(false);
  }, [clearTimer]);

  // Tidy up a pending timer if the component unmounts mid-press.
  useEffect(() => clearTimer, [clearTimer]);

  if (!eligible) return children;

  const probabilities = data?.probabilities;
  // The curve is positional by business day; clamp into range so a review that
  // has run longer than the longest completed one reuses the (capped) tail.
  const probability =
    Array.isArray(probabilities) && probabilities.length > 0
      ? probabilities[Math.min(progress.elapsed, probabilities.length - 1)]
      : null;
  const percent = probability != null ? Math.round(probability * 100) : null;

  return (
    <span
      className="relative inline-flex select-none touch-none [-webkit-touch-callout:none]"
      onMouseDown={startPress}
      onMouseUp={endPress}
      onMouseLeave={endPress}
      onTouchStart={startPress}
      onTouchEnd={endPress}
      onTouchCancel={endPress}
      onContextMenu={(e) => e.preventDefault()}
    >
      {children}
      {revealed && (
        <span
          role="status"
          className="absolute right-0 top-full mt-2 z-30 w-48 rounded-xl border border-amber-200/70 bg-white px-3 py-2.5 text-left shadow-lg animate-fade-in"
        >
          <span className="block text-[10px] font-semibold uppercase tracking-wider text-amber-600">
            Est. probability of Phase 2 referral
          </span>
          {percent != null ? (
            <>
              <span className="block text-xl font-bold leading-tight text-gray-900">
                {percent}%
              </span>
              <span className="block text-[11px] leading-snug text-gray-500">
                at business day {progress.elapsed} of {progress.total}
              </span>
            </>
          ) : (
            <span className="block text-sm text-gray-400">estimating…</span>
          )}
        </span>
      )}
    </span>
  );
}

export default Phase2OddsReveal;
