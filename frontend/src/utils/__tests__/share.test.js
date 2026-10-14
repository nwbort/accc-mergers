import { describe, expect, it } from 'vitest';
import { prefersNativeShare, shareTargets, shareUrl } from '../share';

describe('shareUrl', () => {
  it('makes a site path absolute against the canonical origin', () => {
    expect(shareUrl('/mergers/MN-01016/acme-bidco')).toBe('https://mergers.fyi/mergers/MN-01016/acme-bidco');
  });
});

describe('shareTargets', () => {
  const url = 'https://mergers.fyi/mergers/MN-01016/a-b';
  const title = 'A & B';
  const byId = Object.fromEntries(shareTargets({ url, title }).map((t) => [t.id, t.href]));

  it('offers LinkedIn, Bluesky, X and email, in that order', () => {
    expect(shareTargets({ url, title }).map((t) => t.id)).toEqual(['linkedin', 'bluesky', 'x', 'email']);
  });

  it('encodes the URL and title so an ampersand cannot split the query', () => {
    expect(byId.linkedin).toBe(`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`);
    const x = new URL(byId.x);
    expect(x.searchParams.get('text')).toBe(title);
    expect(x.searchParams.get('url')).toBe(url);
  });

  it('puts the link inside the post text where there is only one field', () => {
    expect(new URL(byId.bluesky).searchParams.get('text')).toBe(`${title}\n${url}`);
    expect(byId.email).toBe(`mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(`${title}\n${url}`)}`);
  });
});

describe('prefersNativeShare', () => {
  const win = (coarse) => ({ matchMedia: () => ({ matches: coarse }) });
  const share = () => {};

  it('uses the share sheet on a touch device that has one', () => {
    expect(prefersNativeShare({ share }, win(true))).toBe(true);
  });

  it('keeps the menu on desktop even where navigator.share exists', () => {
    expect(prefersNativeShare({ share }, win(false))).toBe(false);
  });

  it('keeps the menu where there is no share sheet', () => {
    expect(prefersNativeShare({}, win(true))).toBe(false);
  });
});
