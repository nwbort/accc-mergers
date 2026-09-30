import { beforeEach, describe, expect, it } from 'vitest';
import { getSeenItems, isNewItem, markItemsAsSeen } from '../lastVisit';

describe('lastVisit', () => {
  beforeEach(() => localStorage.clear());

  it('marks items seen', () => {
    expect(isNewItem('MN-1')).toBe(true);
    markItemsAsSeen(['MN-1']);
    expect(isNewItem('MN-1')).toBe(false);
  });

  it('keeps an item that is re-marked from ageing out of the prune', () => {
    markItemsAsSeen(['MN-KEEP']);
    for (let i = 0; i < 120; i++) {
      markItemsAsSeen([`MN-${i}`, 'MN-KEEP']);
    }
    expect(getSeenItems().size).toBe(100);
    expect(isNewItem('MN-KEEP')).toBe(false);
  });
});
