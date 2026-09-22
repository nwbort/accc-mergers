import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import {
  fetchIndustryNode,
  industryDivisionCacheKey,
  readIndustryNode,
} from '../industryNode.js';
import { dataCache } from '../dataCache.js';

// A miniature division file in exactly the shape the generator writes:
// hierarchy metadata plus merger *ids* per node, and the summaries once.
const DIVISION = {
  division: 'B',
  nodes: {
    B: {
      name: 'Mining', level: 'division', parent: null, children: ['06'],
      mergers: ['MN-0002', 'MN-0001'], count: 2,
      phase_1_count: 2, phase_2_count: 0, waiver_count: 0, active_count: 1,
      phase_duration: { average_business_days: 20, completed_count: 1 },
    },
    '06': {
      name: 'Coal Mining', level: 'subdivision', parent: 'B', children: ['060'],
      mergers: ['MN-0002', 'MN-0001'], count: 2,
      phase_1_count: 2, phase_2_count: 0, waiver_count: 0, active_count: 1,
    },
    '060': {
      name: 'Coal Mining', level: 'group', parent: '06', children: ['0600'],
      mergers: ['MN-0001'], count: 1,
      phase_1_count: 1, phase_2_count: 0, waiver_count: 0, active_count: 0,
    },
    '0600': {
      name: 'Coal Mining', level: 'class', parent: '060', children: [],
      mergers: ['MN-0001'], count: 1,
      phase_1_count: 1, phase_2_count: 0, waiver_count: 0, active_count: 0,
    },
    '0700': {
      name: 'Oil and Gas Extraction', level: 'class', parent: '070', children: [],
      mergers: [], count: 0,
      phase_1_count: 0, phase_2_count: 0, waiver_count: 0, active_count: 0,
    },
  },
  mergers: {
    'MN-0001': { merger_id: 'MN-0001', merger_name: 'Alpha', phase: 'Phase 1' },
    'MN-0002': { merger_id: 'MN-0002', merger_name: 'Beta', phase: 'Phase 1' },
  },
};

describe('readIndustryNode', () => {
  it('re-expands merger ids into summaries, in the stored order', () => {
    const node = readIndustryNode(DIVISION, 'B');
    // The generator sorts open reviews first, so the order is load-bearing and
    // cannot be recomputed here — the summaries carry no dates.
    expect(node.mergers.map((m) => m.merger_id)).toEqual(['MN-0002', 'MN-0001']);
    expect(node.mergers[0].merger_name).toBe('Beta');
  });

  it('rebuilds the breadcrumb by walking the parent chain, division first', () => {
    const node = readIndustryNode(DIVISION, '0600');
    expect(node.ancestors.map((a) => a.code)).toEqual(['B', '06', '060']);
    expect(node.ancestors[0]).toEqual({ code: 'B', name: 'Mining', level: 'division' });
    expect(node.parent).toEqual({ code: '060', name: 'Coal Mining', level: 'group' });
  });

  it('gives a division no ancestors and no parent', () => {
    const node = readIndustryNode(DIVISION, 'B');
    expect(node.ancestors).toEqual([]);
    expect(node.parent).toBeNull();
  });

  it('reads each child’s merger count off the sibling node entries', () => {
    const node = readIndustryNode(DIVISION, '060');
    expect(node.children).toEqual([
      { code: '0600', name: 'Coal Mining', level: 'class', merger_count: 1 },
    ]);
  });

  it('defaults an omitted duration block to null', () => {
    // The generator omits these rather than writing null on all 825 nodes, but
    // IndustryDetail reads them as "absent means no completed reviews".
    expect(readIndustryNode(DIVISION, 'B').phase_duration).not.toBeNull();
    expect(readIndustryNode(DIVISION, '06').phase_duration).toBeNull();
    expect(readIndustryNode(DIVISION, 'B').waiver_duration).toBeNull();
  });

  it('handles a node with no mergers', () => {
    const node = readIndustryNode(DIVISION, '0700');
    expect(node.mergers).toEqual([]);
    expect(node.count).toBe(0);
  });

  it('returns null for a code the payload does not hold', () => {
    expect(readIndustryNode(DIVISION, '9999')).toBeNull();
    expect(readIndustryNode(null, 'B')).toBeNull();
    expect(readIndustryNode({}, 'B')).toBeNull();
  });

  it('drops merger ids with no summary rather than rendering blanks', () => {
    const partial = { ...DIVISION, mergers: { 'MN-0001': DIVISION.mergers['MN-0001'] } };
    const node = readIndustryNode(partial, 'B');
    expect(node.mergers.map((m) => m.merger_id)).toEqual(['MN-0001']);
    // count stays the node's own tally, so a partial payload can't quietly
    // understate how big an industry is.
    expect(node.count).toBe(2);
  });

  it('does not hang on a malformed parent cycle', () => {
    const cyclic = {
      nodes: {
        x: { name: 'X', level: 'group', parent: 'y', children: [], mergers: [], count: 0 },
        y: { name: 'Y', level: 'group', parent: 'x', children: [], mergers: [], count: 0 },
      },
      mergers: {},
    };
    expect(readIndustryNode(cyclic, 'x').ancestors.map((a) => a.code)).toEqual(['y']);
  });
});

describe('fetchIndustryNode', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => DIVISION,
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    dataCache.clear();
  });

  it('fetches the division file and rehydrates the node', async () => {
    const node = await fetchIndustryNode('0600');
    expect(fetch).toHaveBeenCalledWith('/data/industries/B.json');
    expect(node.name).toBe('Coal Mining');
  });

  it('costs one request for every node in the same division', async () => {
    // This is the point of the layout: a dozen followed industries under one
    // division, or a page and its parent comparison, share a single fetch.
    await fetchIndustryNode('0600');
    await fetchIndustryNode('060');
    await fetchIndustryNode('B');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(dataCache.has(industryDivisionCacheKey('0600'))).toBe(true);
  });

  it('resolves null when the division file is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404 })));
    expect(await fetchIndustryNode('0600')).toBeNull();
  });

  it('resolves null when the SPA fallback returns HTML with a 200', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => { throw new SyntaxError('Unexpected token <'); },
    })));
    expect(await fetchIndustryNode('0600')).toBeNull();
  });

  it('resolves null when the file loads but holds no such node', async () => {
    expect(await fetchIndustryNode('0601')).toBeNull();
  });
});
