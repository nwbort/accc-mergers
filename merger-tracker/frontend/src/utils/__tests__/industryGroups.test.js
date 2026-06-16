import { describe, expect, it } from 'vitest';
import { groupMergersByPhase, mergerPhase } from '../industryGroups';

const mergers = [
  { merger_id: 'A', phase: 'Phase 1', is_waiver: false },
  { merger_id: 'B', phase: 'Waiver', is_waiver: true },
  { merger_id: 'C', phase: 'Phase 2', is_waiver: false },
  { merger_id: 'D', phase: 'Phase 1', is_waiver: false },
];

describe('groupMergersByPhase', () => {
  it('orders groups Phase 2, Phase 1, Waivers', () => {
    const groups = groupMergersByPhase(mergers);
    expect(groups.map((g) => g.key)).toEqual(['Phase 2', 'Phase 1', 'Waiver']);
  });

  it('counts mergers within each group', () => {
    const byKey = Object.fromEntries(
      groupMergersByPhase(mergers).map((g) => [g.key, g.mergers.length])
    );
    expect(byKey).toEqual({ 'Phase 2': 1, 'Phase 1': 2, 'Waiver': 1 });
  });

  it('skips empty groups', () => {
    const groups = groupMergersByPhase([{ merger_id: 'X', phase: 'Phase 1' }]);
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe('Phase 1');
  });

  it('returns nothing for an empty list', () => {
    expect(groupMergersByPhase([])).toEqual([]);
  });
});

describe('mergerPhase', () => {
  it('prefers the pipeline-provided phase field', () => {
    expect(mergerPhase({ phase: 'Phase 2', is_waiver: false })).toBe('Phase 2');
  });

  it('falls back to is_waiver when phase is absent', () => {
    expect(mergerPhase({ is_waiver: true })).toBe('Waiver');
    expect(mergerPhase({ is_waiver: false })).toBe('Phase 1');
  });
});
