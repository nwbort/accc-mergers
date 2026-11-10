import { beforeEach, describe, expect, it, vi } from 'vitest';
import { pushConfigured, syncTopics, topicChanges } from '../webPush';

describe('pushConfigured', () => {
  it('needs the web app config and a VAPID key', () => {
    const config = { apiKey: 'k', appId: 'a', projectId: 'p' };
    expect(pushConfigured(config, 'v')).toBe(true);
    expect(pushConfigured(config, null)).toBe(false);
    expect(pushConfigured({ ...config, appId: null }, 'v')).toBe(false);
  });
});

describe('topicChanges', () => {
  it('adds and removes against what the same token has', () => {
    expect(topicChanges({ token: 't', topics: ['all', 'merger-MN-1'] }, 't', ['all', 'merger-MN-2'])).toEqual({
      add: ['merger-MN-2'],
      remove: ['merger-MN-1'],
    });
  });

  it('starts over for a new token', () => {
    expect(topicChanges({ token: 'old', topics: ['all'] }, 'new', ['all'])).toEqual({ add: ['all'], remove: [] });
  });
});

describe('syncTopics', () => {
  beforeEach(() => localStorage.clear());

  const ok = () => vi.fn(async () => ({ ok: true }));

  it('sends the changes and records them', async () => {
    const post = ok();
    await syncTopics('t', ['all', 'merger-MN-1'], { post });
    expect(JSON.parse(post.mock.calls[0][1].body)).toEqual({ token: 't', add: ['all', 'merger-MN-1'], remove: [] });
    await syncTopics('t', ['all'], { post });
    expect(JSON.parse(post.mock.calls[1][1].body)).toEqual({ token: 't', add: [], remove: ['merger-MN-1'] });
    await syncTopics('t', ['all'], { post });
    expect(post).toHaveBeenCalledTimes(2);
  });

  it('sends a long list in batches', async () => {
    const post = ok();
    const topics = Array.from({ length: 90 }, (_, i) => `merger-MN-${String(i).padStart(5, '0')}`);
    await syncTopics('t', topics, { post });
    expect(post).toHaveBeenCalledTimes(3);
  });

  it('keeps what got through when a request fails', async () => {
    const topics = Array.from({ length: 50 }, (_, i) => `merger-MN-${String(i).padStart(5, '0')}`);
    let calls = 0;
    const post = vi.fn(async () => ({ ok: ++calls === 1, status: 503 }));
    await expect(syncTopics('t', topics, { post })).rejects.toThrow('503');
    const retry = ok();
    await syncTopics('t', topics, { post: retry });
    expect(JSON.parse(retry.mock.calls[0][1].body).add).toHaveLength(10);
  });
});
