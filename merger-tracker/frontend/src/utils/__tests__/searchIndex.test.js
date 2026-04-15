import { beforeEach, describe, expect, it } from 'vitest';
import { buildSearchIndex, searchMergers, clearSearchIndex } from '../searchIndex';
import { dataCache } from '../dataCache';

// searchIndex uses dataCache under the hood, so flush it before every test.
beforeEach(() => {
  dataCache.clear();
});

const sample = [
  {
    merger_id: 'MN-01019',
    merger_name: 'Ampol / Z Energy',
    acquirers: [{ name: 'Ampol Limited' }],
    targets: [{ name: 'Z Energy' }],
    anzsic_codes: [{ name: 'Petroleum Retailing' }],
  },
  {
    merger_id: 'MN-02020',
    merger_name: 'Woolworths / PFD Food Services',
    acquirers: [{ name: 'Woolworths Group' }],
    targets: [{ name: 'PFD Food Services' }],
    anzsic_codes: [{ name: 'Grocery Wholesaling' }],
  },
  {
    merger_id: 'MN-03030',
    merger_name: 'BHP / Anglo American',
    acquirers: [{ name: 'BHP Billiton' }, null, { name: null }],
    targets: [{ name: 'Anglo American' }],
    anzsic_codes: [{ name: 'Mining' }],
  },
];

describe('buildSearchIndex', () => {
  it('returns a Map keyed by merger_id', () => {
    const index = buildSearchIndex(sample);
    expect(index).toBeInstanceOf(Map);
    expect(index.size).toBe(3);
    expect(index.has('MN-01019')).toBe(true);
    expect(index.has('MN-02020')).toBe(true);
    expect(index.has('MN-03030')).toBe(true);
  });

  it('concatenates name, id, acquirers, targets, and industries into a lowercase string', () => {
    const index = buildSearchIndex(sample);
    const str = index.get('MN-01019');
    expect(str).toBe(
      'ampol / z energy mn-01019 ampol limited z energy petroleum retailing'
    );
  });

  it('ignores acquirers/targets/industries with missing or null names', () => {
    const index = buildSearchIndex(sample);
    const str = index.get('MN-03030');
    expect(str).toContain('bhp billiton');
    expect(str).toContain('anglo american');
    expect(str).toContain('mining');
    // Shouldn't contain 'null' or 'undefined' from bad entries.
    expect(str).not.toContain('null');
    expect(str).not.toContain('undefined');
  });

  it('handles an empty array', () => {
    const index = buildSearchIndex([]);
    expect(index).toBeInstanceOf(Map);
    expect(index.size).toBe(0);
  });

  it('tolerates mergers that are missing optional fields', () => {
    const index = buildSearchIndex([
      { merger_id: 'MN-BARE', merger_name: 'Bare Minimum' },
    ]);
    expect(index.get('MN-BARE')).toBe('bare minimum mn-bare');
  });

  it('returns the cached index on the second call rather than rebuilding', () => {
    const first = buildSearchIndex(sample);
    // Rebuild from a different input — should still get the cached value.
    const second = buildSearchIndex([
      {
        merger_id: 'MN-NEW',
        merger_name: 'Different',
        acquirers: [],
        targets: [],
        anzsic_codes: [],
      },
    ]);
    expect(second).toBe(first);
  });

  it('rebuilds after clearSearchIndex()', () => {
    const first = buildSearchIndex(sample);
    clearSearchIndex();
    const rebuilt = buildSearchIndex([
      { merger_id: 'MN-NEW', merger_name: 'Different' },
    ]);
    expect(rebuilt).not.toBe(first);
    expect(rebuilt.size).toBe(1);
    expect(rebuilt.has('MN-NEW')).toBe(true);
  });
});

describe('searchMergers', () => {
  it('returns all mergers when searchTerm is empty', () => {
    const index = buildSearchIndex(sample);
    expect(searchMergers(sample, '', index)).toEqual(sample);
    expect(searchMergers(sample, null, index)).toEqual(sample);
    expect(searchMergers(sample, undefined, index)).toEqual(sample);
  });

  it('returns all mergers when searchTerm is only whitespace', () => {
    const index = buildSearchIndex(sample);
    expect(searchMergers(sample, '   ', index)).toEqual(sample);
  });

  it('filters by merger name (case-insensitive)', () => {
    const index = buildSearchIndex(sample);
    const result = searchMergers(sample, 'AMPOL', index);
    expect(result).toHaveLength(1);
    expect(result[0].merger_id).toBe('MN-01019');
  });

  it('filters by merger id', () => {
    const index = buildSearchIndex(sample);
    const result = searchMergers(sample, 'MN-02020', index);
    expect(result).toHaveLength(1);
    expect(result[0].merger_id).toBe('MN-02020');
  });

  it('filters by acquirer name', () => {
    const index = buildSearchIndex(sample);
    const result = searchMergers(sample, 'woolworths', index);
    expect(result.map((m) => m.merger_id)).toEqual(['MN-02020']);
  });

  it('filters by target name', () => {
    const index = buildSearchIndex(sample);
    const result = searchMergers(sample, 'anglo american', index);
    expect(result.map((m) => m.merger_id)).toEqual(['MN-03030']);
  });

  it('filters by ANZSIC industry name', () => {
    const index = buildSearchIndex(sample);
    const result = searchMergers(sample, 'petroleum', index);
    expect(result.map((m) => m.merger_id)).toEqual(['MN-01019']);
  });

  it('returns empty array for no matches', () => {
    const index = buildSearchIndex(sample);
    expect(searchMergers(sample, 'xyz-not-a-match', index)).toEqual([]);
  });

  it('trims whitespace around the search term', () => {
    const index = buildSearchIndex(sample);
    const result = searchMergers(sample, '  ampol  ', index);
    expect(result).toHaveLength(1);
  });

  it('skips mergers that are missing from the index', () => {
    const index = new Map();
    // Even if the term exists in merger.merger_name, absence from the index
    // means no match — that is the documented behaviour.
    expect(searchMergers(sample, 'ampol', index)).toEqual([]);
  });
});

describe('clearSearchIndex', () => {
  it('removes the cached index without affecting other cache keys', () => {
    buildSearchIndex(sample);
    dataCache.set('other-key', 'other-value');
    clearSearchIndex();
    expect(dataCache.get('other-key')).toBe('other-value');
    // Calling build again should produce a fresh index (different reference).
    const first = buildSearchIndex(sample);
    const second = buildSearchIndex(sample);
    expect(first).toBe(second); // now cached again
  });
});
