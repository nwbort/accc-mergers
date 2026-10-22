import { beforeEach, describe, expect, it } from 'vitest';
import { loadListPosition, saveListPosition } from '../mergerListPosition';

beforeEach(() => {
  sessionStorage.clear();
});

describe('mergerListPosition', () => {
  it('round-trips a position saved for the same list', () => {
    saveListPosition('q=ampol&sort=name-asc', 3, 1840);
    expect(loadListPosition('q=ampol&sort=name-asc')).toEqual({ page: 3, y: 1840 });
  });

  it('has nothing for a different list — the offset only means anything on the list it was measured on', () => {
    saveListPosition('q=ampol', 3, 1840);
    expect(loadListPosition('q=woolworths')).toBeNull();
    expect(loadListPosition('')).toBeNull();
  });

  it('has nothing when nothing was saved, or what was saved is junk', () => {
    expect(loadListPosition('')).toBeNull();
    sessionStorage.setItem('mergers_list_position', 'not json');
    expect(loadListPosition('')).toBeNull();
    sessionStorage.setItem('mergers_list_position', JSON.stringify({ params: '', page: 0, y: 10 }));
    expect(loadListPosition('')).toBeNull();
  });
});
