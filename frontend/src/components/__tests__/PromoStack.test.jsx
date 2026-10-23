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

describe('PromoStack', () => {
  beforeEach(() => {
    localStorage.clear();
    // The dismiss/click-through pings must not hit the network.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({}));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows only the first campaign', () => {
    renderStack();
    expect(screen.getByRole('link', { name: /First banner/ })).toHaveAttribute('href', '/first');
    expect(screen.queryByText('Second banner')).toBeNull();
  });

  it('brings the next campaign up when one is dismissed, and remembers it', () => {
    const { unmount } = renderStack();
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByText('First banner')).toBeNull();
    expect(screen.getByRole('link', { name: /Second banner/ })).toBeInTheDocument();
    expect(localStorage.getItem('promo_dismissed_first')).toBe('1');

    unmount();
    renderStack();
    expect(screen.queryByText('First banner')).toBeNull();
    expect(screen.getByText('Second banner')).toBeInTheDocument();
  });

  it('skips a campaign dismissed on an earlier visit', () => {
    localStorage.setItem('promo_dismissed_first', '1');
    renderStack();
    expect(screen.getByText('Second banner')).toBeInTheDocument();
  });

  it('renders nothing once every campaign is dismissed', () => {
    const { container } = renderStack();
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(container).toBeEmptyDOMElement();
    expect(localStorage.getItem('promo_dismissed_second')).toBe('1');
  });

  it('renders nothing for an empty list', () => {
    const { container } = renderStack([]);
    expect(container).toBeEmptyDOMElement();
  });
});
