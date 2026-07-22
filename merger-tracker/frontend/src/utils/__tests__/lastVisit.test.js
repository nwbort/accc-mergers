import { afterEach, describe, expect, it } from 'vitest';
import { markItemsAsSeen, sortUnseenFirst } from '../lastVisit';

afterEach(() => {
  localStorage.clear();
});

describe('sortUnseenFirst', () => {
  const items = [
    { merger_id: 'MA-1', label: 'a' },
    { merger_id: 'MA-2', label: 'b' },
    { merger_id: 'MA-3', label: 'c' },
    { merger_id: 'MA-4', label: 'd' },
  ];

  it('returns an empty array for empty or missing input', () => {
    expect(sortUnseenFirst(undefined, (i) => i.merger_id)).toEqual([]);
    expect(sortUnseenFirst([], (i) => i.merger_id)).toEqual([]);
  });

  it('keeps the original order when every item is unseen', () => {
    const result = sortUnseenFirst(items, (i) => i.merger_id);
    expect(result.map((i) => i.merger_id)).toEqual(['MA-1', 'MA-2', 'MA-3', 'MA-4']);
  });

  it('floats unseen items above seen ones, preserving order within each group', () => {
    // MA-1 and MA-3 have already been seen; MA-2 and MA-4 are new.
    markItemsAsSeen(['MA-1', 'MA-3']);

    const result = sortUnseenFirst(items, (i) => i.merger_id);

    // Unseen first (in original order), then seen (in original order).
    expect(result.map((i) => i.merger_id)).toEqual(['MA-2', 'MA-4', 'MA-1', 'MA-3']);
  });

  it('does not mutate the input array', () => {
    markItemsAsSeen(['MA-1']);
    const input = [...items];
    sortUnseenFirst(input, (i) => i.merger_id);
    expect(input.map((i) => i.merger_id)).toEqual(['MA-1', 'MA-2', 'MA-3', 'MA-4']);
  });

  it('treats items with a missing id as seen (they do not float up)', () => {
    const withMissing = [{ label: 'no-id' }, { merger_id: 'MA-9', label: 'new' }];
    const result = sortUnseenFirst(withMissing, (i) => i.merger_id);
    expect(result.map((i) => i.label)).toEqual(['new', 'no-id']);
  });
});
