import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Phase2OddsReveal from '../Phase2OddsReveal';
import { dataCache } from '../../utils/dataCache';

const CACHE_KEY = 'referral-probability-by-day';

// A Phase 1 matter notified 2026-05-18, evaluated as of 2026-06-01 → business
// day 9 of 30 (see BusinessDayProgress.test.jsx for the same calculation).
const phase1Merger = {
  status: 'Under assessment',
  stage: 'Phase 1 - initial assessment',
  effective_notification_datetime: '2026-05-18T12:00:00Z',
  end_of_determination_period: '2026-07-01T12:00:00Z',
};

function renderBadge(merger) {
  return render(
    <Phase2OddsReveal merger={merger}>
      <span data-testid="badge">Under assessment</span>
    </Phase2OddsReveal>
  );
}

describe('Phase2OddsReveal', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));
    // Seed the cache so useFetchData resolves the curve synchronously (no fetch).
    // Index 9 (the matter's business day) carries the distinctive 0.42.
    const probabilities = Array.from({ length: 30 }, (_, i) => (i === 9 ? 0.42 : 0.05));
    dataCache.set(CACHE_KEY, { probabilities });
  });

  afterEach(() => {
    dataCache.clear(CACHE_KEY);
    vi.useRealTimers();
  });

  it('reveals the Phase 2 referral estimate after a long press, then hides it on release', () => {
    renderBadge(phase1Merger);

    // Nothing shown until pressed and held.
    expect(screen.queryByText('42%')).not.toBeInTheDocument();

    fireEvent.mouseDown(screen.getByTestId('badge'));
    act(() => vi.advanceTimersByTime(450));

    expect(screen.getByText('42%')).toBeInTheDocument();
    expect(screen.getByText('at business day 9 of 30')).toBeInTheDocument();

    // Releasing the press dismisses the estimate.
    fireEvent.mouseUp(screen.getByTestId('badge'));
    expect(screen.queryByText('42%')).not.toBeInTheDocument();
  });

  it('does not reveal anything on a quick tap (press released before the hold delay)', () => {
    renderBadge(phase1Merger);

    fireEvent.mouseDown(screen.getByTestId('badge'));
    act(() => vi.advanceTimersByTime(200));
    fireEvent.mouseUp(screen.getByTestId('badge'));
    act(() => vi.advanceTimersByTime(450));

    expect(screen.queryByText('42%')).not.toBeInTheDocument();
  });

  it('stays inert for a Phase 2 matter (renders the child badge untouched)', () => {
    renderBadge({ ...phase1Merger, stage: 'Phase 2 - detailed assessment' });

    fireEvent.mouseDown(screen.getByTestId('badge'));
    act(() => vi.advanceTimersByTime(450));

    expect(screen.queryByText('42%')).not.toBeInTheDocument();
    expect(screen.getByTestId('badge')).toBeInTheDocument();
  });

  it('stays inert once the matter is no longer under assessment', () => {
    renderBadge({ ...phase1Merger, status: 'Assessment completed' });

    fireEvent.mouseDown(screen.getByTestId('badge'));
    act(() => vi.advanceTimersByTime(450));

    expect(screen.queryByText('42%')).not.toBeInTheDocument();
  });

  it('stays silent (no placeholder) when the curve fails to load', async () => {
    // No cache seed + a fetch that rejects → useFetchData surfaces an error.
    dataCache.clear(CACHE_KEY);
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockRejectedValue(new Error('network down'));

    renderBadge(phase1Merger);

    // Let the rejected fetch settle into error state.
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    fireEvent.mouseDown(screen.getByTestId('badge'));
    act(() => vi.advanceTimersByTime(450));

    expect(screen.queryByText('42%')).not.toBeInTheDocument();
    expect(screen.queryByText('estimating…')).not.toBeInTheDocument();

    fetchSpy.mockRestore();
  });

  it('stays inert for a waiver', () => {
    renderBadge({ ...phase1Merger, is_waiver: true, stage: 'Waiver application' });

    fireEvent.mouseDown(screen.getByTestId('badge'));
    act(() => vi.advanceTimersByTime(450));

    expect(screen.queryByText('42%')).not.toBeInTheDocument();
  });
});
