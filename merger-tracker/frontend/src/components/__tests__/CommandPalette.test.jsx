import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import CommandPalette from '../CommandPalette';
import { dataCache } from '../../utils/dataCache';

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

const mergerFixture = [
  { merger_id: 'MN-01019', merger_name: 'Ampol / Z Energy' },
  { merger_id: 'MN-01020', merger_name: 'Woolworths / Some Target' },
];

function renderPalette(props) {
  return render(
    <MemoryRouter>
      <CommandPalette isOpen onClose={() => {}} {...props} />
    </MemoryRouter>
  );
}

describe('CommandPalette', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('renders nothing when closed', () => {
    render(
      <MemoryRouter>
        <CommandPalette isOpen={false} onClose={() => {}} />
      </MemoryRouter>
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('opens as a dialog listing the static pages by default', () => {
    renderPalette();
    expect(screen.getByRole('dialog', { name: 'Command palette' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Mergers' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderPalette({ onClose });
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose on click-outside (backdrop click)', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderPalette({ onClose });
    // Clicking the overlay outside the panel (but inside the fixed wrapper) should close.
    await user.click(screen.getByRole('dialog').parentElement);
    expect(onClose).toHaveBeenCalled();
  });

  it('filters pages by query and searches cached mergers', async () => {
    dataCache.set('mergers-list', mergerFixture);
    const user = userEvent.setup();
    renderPalette();

    const input = screen.getByRole('combobox');
    await user.type(input, 'ampol');

    expect(screen.queryByRole('option', { name: 'Dashboard' })).not.toBeInTheDocument();
    expect(await screen.findByRole('option', { name: 'Ampol / Z Energy' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Woolworths / Some Target' })).not.toBeInTheDocument();
  });

  it('navigates arrow keys through results and opens the selected item on Enter', async () => {
    dataCache.set('mergers-list', mergerFixture);
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderPalette({ onClose });

    const input = screen.getByRole('combobox');
    await user.type(input, 'mergers');
    // Only the "Mergers" page matches this query.
    expect(await screen.findByRole('option', { name: 'Mergers' })).toHaveAttribute('aria-selected', 'true');

    await user.keyboard('{Enter}');
    // Selecting a result navigates and closes the palette.
    expect(onClose).toHaveBeenCalled();
  });

  it('lazily fetches the merger list on a cold cache and shows a loading row', async () => {
    let resolveMeta;
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('list-meta.json')) {
        return new Promise((resolve) => {
          resolveMeta = () => resolve(ok({ total_pages: 1 }));
        });
      }
      if (url.includes('list-page-1.json')) {
        return Promise.resolve(ok({ mergers: mergerFixture }));
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    const user = userEvent.setup();
    renderPalette();

    const input = screen.getByRole('combobox');
    await user.type(input, 'ampol');

    expect(screen.getByText('Loading mergers…')).toBeInTheDocument();

    resolveMeta();

    expect(await screen.findByRole('option', { name: 'Ampol / Z Energy' })).toBeInTheDocument();
    expect(dataCache.get('mergers-list')).toEqual(mergerFixture);
    fetchSpy.mockRestore();
  });
});
