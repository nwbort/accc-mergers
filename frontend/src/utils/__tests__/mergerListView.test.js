import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { loadListView, saveListView } from '../mergerListView';

beforeEach(() => {
  localStorage.clear();
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe('mergerListView', () => {
  it('defaults to cards and round-trips a saved choice', () => {
    expect(loadListView()).toBe('cards');
    saveListView('table');
    expect(loadListView()).toBe('table');
  });

  it('falls back to cards for anything it does not recognise', () => {
    localStorage.setItem('mergers_list_view', 'grid');
    expect(loadListView()).toBe('cards');
  });

  it('survives storage that throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    expect(() => saveListView('table')).not.toThrow();
    expect(loadListView()).toBe('cards');
  });
});
