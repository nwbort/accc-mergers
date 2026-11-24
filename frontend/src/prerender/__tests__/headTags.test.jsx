// @vitest-environment node
// Server-side, so react-helmet-async fills its context instead of the DOM.
import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { HelmetProvider } from 'react-helmet-async';
import SEO from '../../components/SEO';
import { mergerMeta } from '../../utils/pageMeta.js';
import { renderPage } from '../../../prerender.js';
import template from '../../../index.html?raw';

// What identifies a head tag: meta by name/property, link by rel, script by type.
function key(tag) {
  const attr = (name) => tag.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1];
  if (tag.startsWith('<meta')) return attr('name') ?? attr('property') ?? null;
  if (tag.startsWith('<link')) return `link:${attr('rel')}`;
  if (tag.startsWith('<script')) return `script:${attr('type') ?? 'js'}`;
  return null;
}
const headTags = (html) =>
  [...html.slice(0, html.indexOf('</head>')).matchAll(/<(?:meta|link|script)\b[^>]*>/g)].map(([t]) => t);

// Every tag <SEO> can write, from <SEO> itself: rendered with every prop set.
function seoKeys() {
  const context = {};
  renderToStaticMarkup(
    <HelmetProvider context={context}>
      <SEO
        title="t"
        description="d"
        url="/x"
        image="https://mergers.fyi/og/x.png"
        imageAlt="a"
        type="article"
        publishedTime="2026-01-01"
        modifiedTime="2026-01-02"
        section="s"
        structuredData={[{ '@type': 'Thing' }]}
      />
    </HelmetProvider>,
  );
  const { meta, link, script } = context.helmet;
  return new Set(headTags(`${meta}${link}${script}</head>`).map(key).filter(Boolean));
}

// react-helmet-async owns every tag marked data-rh: on mount it keeps an
// identical one and removes the rest. So a marked tag <SEO> doesn't write
// would vanish on mount, and an unmarked one it does write would be doubled.
function expectMarkedExactlyWhereSeoWrites(html, label) {
  const managed = seoKeys();
  expect(managed.size).toBeGreaterThan(10);
  for (const tag of headTags(html)) {
    const k = key(tag);
    if (!k) continue;
    expect(tag.includes('data-rh="true"'), `${label}: ${tag}`).toBe(managed.has(k));
  }
}

describe('head tags handed to Helmet', () => {
  it('in index.html, the fallback shell and template', () => {
    expectMarkedExactlyWhereSeoWrites(template, 'index.html');
  });

  it('in a prerendered page, article tags and JSON-LD included', () => {
    const meta = mergerMeta({
      merger_id: 'MN-01016',
      merger_name: 'A - B',
      effective_notification_datetime: '2026-01-01T12:00:00Z',
      determination_publication_date: '2026-02-01T12:00:00Z',
      anzsic_codes: [{ name: 'Retail' }],
    });
    const html = renderPage(template, meta, '');
    expect(html).toContain('article:published_time');
    expectMarkedExactlyWhereSeoWrites(html, 'merger page');
  });
});
