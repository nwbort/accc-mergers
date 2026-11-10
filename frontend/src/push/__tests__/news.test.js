import { describe, expect, it } from 'vitest';
import { describeNews, findNews } from '../news';
import { getEventKey, timelineEventsFromMerger } from '../../utils/trackedEvents';

const now = new Date('2026-11-06T00:00:00Z');

const merger = (events, extra = {}) => ({
  merger_id: 'MN-01016',
  merger_name: 'Acme / Bolt',
  status: 'Assessment completed',
  accc_determination: 'Approved',
  events,
  ...extra,
});

const notified = { date: '2026-10-01T12:00:00Z', title: 'Merger notified' };
const determined = { date: '2026-11-05T12:00:00Z', title: 'Phase 1 determination', display_title: 'Approved' };

const files = (map) => async (url) => map[url] ?? null;
const keysOf = (m) => timelineEventsFromMerger(m).map(getEventKey);

describe('findNews', () => {
  it('announces an event the panel has never shown', async () => {
    const before = merger([notified]);
    const after = merger([notified, determined]);
    const { news, quiet } = await findNews(
      { trackedMergerIds: ['MN-01016'], known: keysOf(before) },
      { fetch: files({ '/data/mergers/MN-01016.json': after }), now },
    );
    expect(quiet).toEqual([]);
    expect(news).toEqual([
      expect.objectContaining({ name: 'Acme / Bolt', line: 'Approved', url: '/mergers/MN-01016' }),
    ]);
  });

  it('leaves out what was seen, shown in the panel or already announced', async () => {
    const m = merger([notified, determined]);
    const [a, b] = keysOf(m);
    const fetch = files({ '/data/mergers/MN-01016.json': m });
    for (const state of [{ seen: [a, b] }, { known: [a, b] }, { seen: [a], notified: [b] }]) {
      const { news } = await findNews({ trackedMergerIds: ['MN-01016'], ...state }, { fetch, now });
      expect(news).toEqual([]);
    }
  });

  it('takes in a newly followed merger quietly, as the panel marks its history seen', async () => {
    const m = merger([notified, determined]);
    const { news, quiet } = await findNews(
      { trackedMergerIds: ['MN-01016'] },
      { fetch: files({ '/data/mergers/MN-01016.json': m }), now },
    );
    expect(news).toEqual([]);
    expect(quiet).toEqual(keysOf(m));
  });

  it('announces a re-filing once, unless the page has already followed it', async () => {
    const m = merger([notified], { related_merger: { merger_id: 'MN-02000', relationship: 'refiled_as' } });
    const fetch = files({ '/data/mergers/MN-01016.json': m });
    const state = { trackedMergerIds: ['MN-01016'], known: keysOf(m) };
    const { news } = await findNews(state, { fetch, now });
    expect(news).toEqual([expect.objectContaining({ line: 'Re-filed as MN-02000', url: '/mergers/MN-02000' })]);
    const after = await findNews({ ...state, notified: [news[0].key] }, { fetch, now });
    expect(after.news).toEqual([]);
    const done = await findNews({ ...state, autoTrackLinks: ['MN-01016->MN-02000'] }, { fetch, now });
    expect(done.news).toEqual([]);
  });

  it('announces a new filing in a followed industry, reading its division file once', async () => {
    const payload = {
      division: 'H',
      nodes: {
        H: { name: 'Accommodation and Food Services', level: 'division', children: ['45'], mergers: ['MN-1', 'MN-2'] },
        45: { name: 'Food and Beverage Services', level: 'subdivision', parent: 'H', mergers: ['MN-2'] },
      },
      mergers: {
        'MN-1': { merger_id: 'MN-1', merger_name: 'Old', notification_date: '2026-09-01' },
        'MN-2': { merger_id: 'MN-2', merger_name: 'Cafe deal', notification_date: '2026-11-05' },
      },
    };
    const urls = [];
    const fetch = async (url) => {
      urls.push(url);
      return url === '/data/industries/H.json' ? payload : null;
    };
    const oldKey = 'ind_H_MN-1_2026-09-01_New merger filed';
    const { news } = await findNews(
      {
        trackedIndustries: [{ code: 'H', name: 'Accommodation' }, { code: '45', name: 'Food' }],
        known: [oldKey, 'ind_45_MN-2_2026-11-05_New merger filed'],
      },
      { fetch, now },
    );
    expect(urls).toEqual(['/data/industries/H.json']);
    expect(news).toEqual([
      expect.objectContaining({
        name: 'Accommodation and Food Services',
        line: 'New merger filed: Cafe deal',
        url: '/mergers/MN-2',
      }),
    ]);
  });

  it('leaves an industry event to the merger when that merger is followed too', async () => {
    const payload = {
      division: 'G',
      nodes: { G: { name: 'Retail Trade', level: 'division', mergers: ['MN-01016', 'MN-9'] } },
      mergers: {
        'MN-01016': { merger_id: 'MN-01016', merger_name: 'Acme / Bolt', determination_date: '2026-11-05' },
        'MN-9': { merger_id: 'MN-9', merger_name: 'Older', notification_date: '2026-01-01' },
      },
    };
    const m = merger([notified, determined]);
    const { news } = await findNews(
      {
        trackedMergerIds: ['MN-01016'],
        trackedIndustries: [{ code: 'G', name: 'Retail' }],
        known: [keysOf(m)[0], 'ind_G_MN-9_2026-01-01_New merger filed'],
      },
      { fetch: files({ '/data/mergers/MN-01016.json': m, '/data/industries/G.json': payload }), now },
    );
    expect(news.map((item) => item.name)).toEqual(['Acme / Bolt']);
  });

  it('announces a matter newly in Phase 2 when following every Phase 2 matter', async () => {
    const fetch = files({
      '/data/phase2.json': { current: [{ merger_id: 'MN-1', merger_name: 'Old' }, { merger_id: 'MN-3', merger_name: 'New' }] },
    });
    const { news } = await findNews({ autoTrackPhase2: true, autoTrackedPhase2Ids: ['MN-1'] }, { fetch, now });
    expect(news).toEqual([expect.objectContaining({ name: 'New', line: 'Moved to Phase 2', url: '/mergers/MN-3' })]);
    // Only just switched on: what's there already isn't news.
    const fresh = await findNews({ autoTrackPhase2: true }, { fetch, now });
    expect(fresh.news).toEqual([]);
    expect(fresh.quiet).toEqual(['phase2_MN-1', 'phase2_MN-3']);
  });
});

describe('describeNews', () => {
  const item = (name, line, url = '/mergers/MN-1') => ({ key: `${name}${line}`, name, line, url });

  it('says one item as itself', () => {
    expect(describeNews([item('Acme / Bolt', 'Approved')])).toEqual({
      title: 'Acme / Bolt',
      body: 'Approved',
      url: '/mergers/MN-1',
    });
  });

  it('lists several under one name, and counts several across names', () => {
    expect(describeNews([item('Acme', 'A'), item('Acme', 'B')]).body).toBe('A\nB');
    const many = describeNews([
      item('A', '1', '/mergers/MN-1'),
      item('B', '2', '/mergers/MN-2'),
      item('C', '3'),
      item('D', '4'),
      item('E', '5'),
    ]);
    expect(many.title).toBe('5 updates on what you follow');
    expect(many.body).toBe('A: 1\nB: 2\nC: 3\nD: 4\nand 1 more');
    expect(many.url).toBe('/');
  });
});
