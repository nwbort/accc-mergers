import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PromoStack from '../PromoStack';

const PROMOS = [
  { campaign: 'first', to: '/first', title: 'First banner' },
  { campaign: 'second', to: '/second', title: 'Second banner' },
];

function renderStack(promos = PROMOS) {
  return render(
    <MemoryRouter>
      <PromoStack promos={promos} />
    </MemoryRouter>,
  );
}

function bannerTitles() {
  return screen.queryAllByRole('heading').map((h) => h.textContent);
}

describe('PromoStack', () => {
  beforeEach(() => {
    localStorage.clear();
    // The dismiss/click-through pings must not hit the network.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({}));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('stacks every campaign in list order', () => {
    renderStack();
    expect(bannerTitles()).toEqual(['First banner', 'Second banner']);
    expect(screen.getByRole('link', { name: /First banner/ })).toHaveAttribute('href', '/first');
    expect(screen.getByRole('link', { name: /Second banner/ })).toHaveAttribute('href', '/second');
  });

  it('drops a dismissed campaign, closes the gap, and remembers it', () => {
    const { unmount } = renderStack();
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss: First banner' }));
    expect(bannerTitles()).toEqual(['Second banner']);
    expect(localStorage.getItem('promo_dismissed_first')).toBe('1');
    expect(localStorage.getItem('promo_dismissed_second')).toBeNull();

    unmount();
    renderStack();
    expect(bannerTitles()).toEqual(['Second banner']);
  });

  it('dismisses a lower banner without touching the ones above', () => {
    renderStack();
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss: Second banner' }));
    expect(bannerTitles()).toEqual(['First banner']);
    expect(localStorage.getItem('promo_dismissed_second')).toBe('1');
  });

  it('skips a campaign dismissed on an earlier visit', () => {
    localStorage.setItem('promo_dismissed_first', '1');
    renderStack();
    expect(bannerTitles()).toEqual(['Second banner']);
  });

  it('renders nothing once every campaign is dismissed', () => {
    const { container } = renderStack();
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss: First banner' }));
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss: Second banner' }));
    expect(container).toBeEmptyDOMElement();
  });

  it('links an external campaign out in a new tab', () => {
    renderStack([{ campaign: 'ext', href: 'https://example.com/live', title: 'External' }]);
    const link = screen.getByRole('link', { name: /External/ });
    expect(link).toHaveAttribute('href', 'https://example.com/live');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('shows what resolve returns for now, and hides a campaign it returns null for', () => {
    renderStack([
      { campaign: 'timed', to: '/t', title: 'Fallback', resolve: () => ({ title: 'Right now' }) },
      { campaign: 'over', to: '/o', title: 'Over', resolve: () => null },
      ...PROMOS,
    ]);
    expect(bannerTitles()).toEqual(['Right now', 'First banner', 'Second banner']);
  });

  it('re-reads a timed campaign as the clock moves', () => {
    vi.useFakeTimers();
    try {
      let calls = 0;
      renderStack([{ campaign: 'timed', to: '/t', resolve: () => ({ title: `Tick ${calls++}` }) }]);
      expect(bannerTitles()).toEqual(['Tick 0']);
      act(() => vi.advanceTimersByTime(60_000));
      expect(bannerTitles()).toEqual(['Tick 1']);
    } finally {
      vi.useRealTimers();
    }
  });

  it('renders nothing for an empty list', () => {
    const { container } = renderStack([]);
    expect(container).toBeEmptyDOMElement();
  });
});
