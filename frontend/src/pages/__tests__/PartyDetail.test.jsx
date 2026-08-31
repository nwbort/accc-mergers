import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import PartyDetail from '../PartyDetail';
import { dataCache } from '../../utils/dataCache';
import { partyShardName } from '../../utils/shard';

// Party records are packed into shard buckets rather than one file per party,
// so the page has to fetch the right bucket and pick the right record out of
// it. Getting either half wrong fails quietly — the wrong bucket 404s, and a
// bad lookup renders an empty page — so both are pinned here.

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

function notFound() {
  return { ok: false, status: 404, json: () => Promise.resolve(null) };
}

function party(id, name, overrides = {}) {
  return {
    id,
    canonical_name: name,
    members: [{ name, identifier: '', identifier_type: '' }],
    mergers: { acquirer: [], target: [], other: [] },
    merger_count: 0,
    phase_1_count: 0,
    phase_2_count: 0,
    waiver_count: 0,
    active_count: 0,
    phase_duration: null,
    waiver_duration: null,
    ...overrides,
  };
}

function bucket(...records) {
  return {
    shard: 0,
    shard_count: 256,
    parties: Object.fromEntries(records.map((r) => [r.id, r])),
  };
}

/** Renders /parties/:id with `respond` deciding what each URL returns. */
function renderParty(id, respond) {
  const fetchSpy = vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation((url) => Promise.resolve(respond(url)));
  render(
    <HelmetProvider>
      <MemoryRouter initialEntries={[`/parties/${id}`]}>
        <Routes>
          <Route path="/parties/:id" element={<PartyDetail />} />
        </Routes>
      </MemoryRouter>
    </HelmetProvider>
  );
  return fetchSpy;
}

describe('PartyDetail', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('fetches the bucket the id hashes into', async () => {
    const fetchSpy = renderParty('coles', (url) =>
      url.includes('/data/parties/') ? ok(bucket(party('coles', 'Coles Group'))) : ok({})
    );

    await screen.findByRole('heading', { name: 'Coles Group' });

    const partyUrls = fetchSpy.mock.calls
      .map(([url]) => url)
      .filter((url) => url.startsWith('/data/parties/'));
    expect(partyUrls).toEqual([`/data/parties/${partyShardName('coles')}`]);
  });

  it('picks the right record when the bucket holds several parties', async () => {
    // p-15 and p-60 genuinely collide into the same bucket, so this proves the
    // page keys into the bucket rather than taking whatever is first.
    const shared = bucket(party('p-15', 'First Party'), party('p-60', 'Second Party'));
    expect(partyShardName('p-15')).toBe(partyShardName('p-60'));

    renderParty('p-60', (url) =>
      url.includes('/data/parties/') ? ok(shared) : ok({})
    );

    await screen.findByRole('heading', { name: 'Second Party' });
    expect(screen.queryByRole('heading', { name: 'First Party' })).not.toBeInTheDocument();
  });

  it('shows "not found" when the bucket loads but holds no such party', async () => {
    // The case that only exists because of sharding: the file is there and
    // parses fine, but this id was never packed into it.
    renderParty('ghost-party', (url) =>
      url.includes('/data/parties/') ? ok(bucket(party('someone-else', 'Someone Else'))) : ok({})
    );

    expect(await screen.findByText('Party not found')).toBeInTheDocument();
    expect(screen.getByText(/ghost-party/)).toBeInTheDocument();
  });

  it('shows "not found" when the bucket itself is missing', async () => {
    renderParty('ghost-party', () => notFound());

    expect(await screen.findByText('Party not found')).toBeInTheDocument();
  });

  it('shows a load error rather than "not found" when the fetch fails outright', async () => {
    renderParty('coles', () => ({
      ok: false,
      status: 500,
      json: () => Promise.resolve(null),
    }));

    expect(await screen.findByText('Error loading party')).toBeInTheDocument();
  });
});
