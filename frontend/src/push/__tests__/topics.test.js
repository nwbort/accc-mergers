import { describe, expect, it } from 'vitest';
import { industryTopic, mergerTopic, pushTopics } from '../topics';

// The names are shared with scripts/push/fcm.py (tests/test_push_fcm.py) and
// the Android app's notify/Push.kt, which pin the same values.
describe('push topics', () => {
  it('names a merger and an industry division file', () => {
    expect(mergerTopic('MN-01016')).toBe('merger-MN-01016');
    expect(industryTopic('4520')).toBe('industry-H');
    expect(industryTopic('G')).toBe('industry-G');
    expect(industryTopic('9999')).toBe('industry-_orphans');
  });

  it('subscribes to nothing when nothing is followed', () => {
    expect(pushTopics({})).toEqual([]);
  });

  it('lists every followed file once, with all, and list only for Phase 2', () => {
    expect(
      pushTopics({ trackedMergerIds: ['MN-01016', 'WA-15020'], trackedIndustryCodes: ['4520', '45', 'G'] }),
    ).toEqual(['all', 'industry-G', 'industry-H', 'merger-MN-01016', 'merger-WA-15020']);
    expect(pushTopics({ autoTrackPhase2: true })).toEqual(['all', 'list']);
  });
});
