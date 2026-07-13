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

const partiesFixture = {
  parties: [
    { id: 'coles', name: 'Coles Group', merger_count: 9 },
    { id: 'ampol-limited', name: 'Ampol Limited', merger_count: 3 },
  ],
  total_parties: 2,
};

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

  it('searches cached parties and lists them in a Parties group', async () => {
    dataCache.set('parties-list', partiesFixture);
    const user = userEvent.setup();
    renderPalette();

    const input = screen.getByRole('combobox');
    await user.type(input, 'coles');

    expect(await screen.findByRole('option', { name: 'Coles Group' })).toBeInTheDocument();
    expect(screen.getByText('Parties')).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Ampol Limited' })).not.toBeInTheDocument();
  });

  it('lazily fetches the parties list on a cold cache', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (url.includes('parties.json')) {
        return Promise.resolve(ok(partiesFixture));
      }
      if (url.includes('list-meta.json')) {
        return Promise.resolve(ok({ total_pages: 1 }));
      }
      if (url.includes('list-page-1.json')) {
        return Promise.resolve(ok({ mergers: mergerFixture }));
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    const user = userEvent.setup();
    renderPalette();

    const input = screen.getByRole('combobox');
    await user.type(input, 'coles');

    expect(await screen.findByRole('option', { name: 'Coles Group' })).toBeInTheDocument();
    expect(dataCache.get('parties-list')).toEqual(partiesFixture);
    fetchSpy.mockRestore();
  });

  it('shares the result budget so few parties leave room for more mergers', async () => {
    // 20 mergers and 2 parties all match "acme". The combined budget is 8, so
    // the two parties should leave room for six mergers (rather than capping
    // mergers at the even half of four).
    const manyMergers = Array.from({ length: 20 }, (_, i) => ({
      merger_id: `MN-${1000 + i}`,
      merger_name: `Acme Deal ${i}`,
    }));
    const twoParties = {
      parties: [
        { id: 'acme-one', name: 'Acme One', merger_count: 2 },
        { id: 'acme-two', name: 'Acme Two', merger_count: 1 },
      ],
      total_parties: 2,
    };
    dataCache.set('mergers-list', manyMergers);
    dataCache.set('parties-list', twoParties);

    const user = userEvent.setup();
    renderPalette();

    const input = screen.getByRole('combobox');
    await user.type(input, 'acme');

    await screen.findByText('Parties');
    // Two party rows...
    expect(screen.getByRole('option', { name: 'Acme One' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Acme Two' })).toBeInTheDocument();
    // ...and six merger rows (borrowing the two the parties didn't use).
    const mergerRows = screen
      .getAllByRole('option')
      .filter((el) => /^Acme Deal /.test(el.textContent));
    expect(mergerRows).toHaveLength(6);
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
