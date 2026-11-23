// @vitest-environment node
// Rendered as the build renders it: in Node, with no window or storage.
import { describe, expect, it } from 'vitest';
import { COMPONENT_ROUTES, renderFooter, renderHome, renderStaticRoute } from '../renderStatic.jsx';
import { STATIC_PAGE_META } from '../../utils/pageMeta.js';
import realStats from '../../../public/data/stats.json';

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

  it('states every fact its ProfilePage JSON-LD claims', () => {
    // Structured data should describe what the page shows, not add to it.
    const text = renderStaticRoute('/nick-twort').replace(/<[^>]+>/g, '').replace(/&#x27;|&#39;/g, "'");
    const person = STATIC_PAGE_META['/nick-twort'].structuredData[0].mainEntity;
    for (const fact of [
      person.name,
      person.worksFor.name,
      person.workLocation.address.addressLocality,
      'Principal',
    ]) {
      expect(text, fact).toContain(fact);
    }
    for (const url of person.sameAs) {
      expect(renderStaticRoute('/nick-twort'), url).toContain(`href="${url}"`);
    }
  });

  it('renders the top of the dashboard with its own cards, labels and all', () => {
    const html = renderHome({
      total_mergers: 10,
      total_waivers: 4,
      by_status: { 'Under assessment': 2 },
      phase_duration: { average_business_days: 20, median_business_days: 18 },
      recent_determinations: [
        { merger_id: 'WA-10010', merger_name: 'Enverus - Spatial', determination: 'Approved', determination_date: '2026-11-20', is_waiver: true },
      ],
      recent_mergers: [
        { merger_id: 'MN-65005', merger_name: 'IAG - RAC', accc_determination: 'Not approved', is_appeal: true, under_appeal: true },
        { merger_id: 'MN-65005', merger_name: 'IAG - RAC', accc_determination: 'Not approved', effective_notification_datetime: '2026-06-01T12:00:00Z' },
      ],
    });
    expect(html).toMatch(/<h1 class="sr-only">Australian merger tracker dashboard<\/h1>/);
    expect(html).toContain('2 under assessment');
    expect(html).toContain('Recent determinations');
    // A waiver is labelled as one, and an appeal card as an appeal rather than
    // as a fresh notification carrying the ACCC's decision.
    expect(html).toMatch(/aria-label="Merger type: Waiver application"/);
    expect(html).toContain('Under appeal');
    expect(html).toContain('Notified 01/06/2026');
    // A build has no visitor, so nothing on it is "new".
    expect(html).not.toContain('New item since last visit');
  });

  it('renders the real stats.json without throwing, linking every recent matter', () => {
    const html = renderHome(realStats);
    for (const m of [...realStats.recent_determinations, ...realStats.recent_mergers]) {
      expect(html, m.merger_id).toContain(`href="/mergers/${m.merger_id}/`);
    }
  });

  it('renders the footer with a plain link to the author page', () => {
    const html = renderFooter();
    expect(html).toMatch(/<footer[\s>]/);
    expect(html).toContain('<a class="');
    expect(html).toMatch(/<a [^>]*href="\/nick-twort"[^>]*>Nick Twort<\/a>/);
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
