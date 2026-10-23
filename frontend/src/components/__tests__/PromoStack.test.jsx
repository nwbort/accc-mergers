import { fireEvent, render, screen } from '@testing-library/react';
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

  it('renders nothing for an empty list', () => {
    const { container } = renderStack([]);
    expect(container).toBeEmptyDOMElement();
  });
});
