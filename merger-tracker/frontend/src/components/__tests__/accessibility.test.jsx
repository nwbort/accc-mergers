import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeAll, describe, expect, it } from 'vitest';
import AppealBadge from '../AppealBadge';
import NewBadge from '../NewBadge';
import RefiledBadge from '../RefiledBadge';
import StatusBadge from '../StatusBadge';
import WaiverBadge from '../WaiverBadge';
import Navbar from '../Navbar';
import { TrackingProvider } from '../../context/TrackingContext';

/**
 * Guards for accessibility properties that are easy to undo by accident,
 * because nothing about the rendered page looks different when they break.
 */
describe('accessibility invariants', () => {
  // Navbar measures itself to pick a layout; jsdom has no ResizeObserver, and
  // every probe measures 0 wide there, so it settles on the full-width nav.
  beforeAll(() => {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  });

  // These badges appear once per row in the merger tables. role="status" makes
  // each one a live region, so re-rendering a filtered list would announce
  // every badge on it.
  const badges = [
    ['AppealBadge', <AppealBadge key="a" />],
    ['NewBadge', <NewBadge key="n" />],
    ['RefiledBadge', <RefiledBadge key="r" />],
    ['WaiverBadge', <WaiverBadge key="w" />],
    ['StatusBadge', <StatusBadge key="s" status="Under assessment" />],
  ];

  it.each(badges)('%s is not a live region', (_name, element) => {
    const { container } = render(element);
    expect(container.querySelector('[role="status"]')).toBeNull();
    expect(container.querySelector('[aria-live]')).toBeNull();
    // ...but still carries an accessible name.
    expect(screen.getByRole('img')).toHaveAccessibleName(/\S/);
  });

  it('marks the active navbar link with aria-current', () => {
    render(
      <MemoryRouter initialEntries={['/mergers']}>
        <TrackingProvider>
          <Navbar onOpenSearch={() => {}} />
        </TrackingProvider>
      </MemoryRouter>
    );
    const active = screen.getAllByRole('link', { name: 'Mergers' });
    expect(active.some((link) => link.getAttribute('aria-current') === 'page')).toBe(true);
    const dashboard = screen.getAllByRole('link', { name: 'Dashboard' });
    expect(dashboard.every((link) => !link.hasAttribute('aria-current'))).toBe(true);
  });

  it('gives the navbar landmark a name, since the mobile menu adds a second nav', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <TrackingProvider>
          <Navbar onOpenSearch={() => {}} />
        </TrackingProvider>
      </MemoryRouter>
    );
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
  });
});
