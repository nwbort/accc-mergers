import { describe, expect, it } from 'vitest';
import { COMPONENT_ROUTES, renderStaticRoute } from '../renderStatic.jsx';
import { STATIC_PAGE_META } from '../../utils/pageMeta.js';

describe('renderStaticRoute', () => {
  it('only claims routes the shared meta table knows', () => {
    for (const path of COMPONENT_ROUTES) {
      expect(STATIC_PAGE_META[path], path).toBeTruthy();
    }
  });

  it('renders the author page itself, not its meta description', () => {
    const html = renderStaticRoute('/nick-twort');
    expect(html).toMatch(/<h1[^>]*>Nick Twort<\/h1>/);
    expect(html).toContain('Overview');
    // <SEO> writes to Helmet's context, never into the body markup.
    expect(html).not.toContain('application/ld+json');
  });

  it('renders the privacy and copyright pages', () => {
    expect(renderStaticRoute('/privacy')).toContain('<h1');
    expect(renderStaticRoute('/copyright')).toContain('CC BY 4.0');
  });

  it('renders commentary from the data it is handed', () => {
    const html = renderStaticRoute('/commentary', {
      commentary: {
        items: [
          {
            merger_id: 'MN-01037',
            merger_name: 'Anglo American - Teck Resources',
            status: 'Assessment completed',
            accc_determination: 'Approved',
            effective_notification_datetime: '2025-10-24T12:00:00Z',
            comments: [{ commentary: 'Cleared with **no** overlaps.', date: '2026-01-19' }],
          },
        ],
      },
    });
    expect(html).toContain('href="/mergers/MN-01037/anglo-american-teck-resources"');
    expect(html).toContain('Cleared with <strong>no</strong> overlaps.');
    expect(html).toContain('1 entry');
  });

  it('returns null for a route it does not render', () => {
    expect(renderStaticRoute('/analysis')).toBeNull();
  });
});
