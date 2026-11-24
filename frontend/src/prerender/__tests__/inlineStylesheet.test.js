import { describe, expect, it } from 'vitest';
import { inlineStylesheet } from '../../../prerender.js';

// Only the prerendered homepage carries its stylesheet inline (issue #1172);
// every other page links the immutable /assets copy.
const template = [
  '<head>',
  '<link rel="preload" as="font" href="/fonts/inter-latin.woff2" crossorigin />',
  '<link rel="stylesheet" crossorigin href="/assets/index-abc123.css">',
  '</head>',
].join('\n');

describe('inlineStylesheet', () => {
  it('swaps the stylesheet link for the file it names, inline', () => {
    const asked = [];
    const html = inlineStylesheet(template, (file) => {
      asked.push(file);
      return 'body{margin:0}';
    });
    expect(asked).toEqual(['assets/index-abc123.css']);
    expect(html).toContain('<style>body{margin:0}</style>');
    expect(html).not.toContain('rel="stylesheet"');
    expect(html).toContain('rel="preload"');
  });

  it('keeps a `$` in the CSS literally', () => {
    const html = inlineStylesheet(template, () => '.a:after{content:"$&$1"}');
    expect(html).toContain('<style>.a:after{content:"$&$1"}</style>');
  });

  it('leaves the link in place when the file cannot be read', () => {
    const html = inlineStylesheet(template, () => {
      throw new Error('ENOENT');
    });
    expect(html).toBe(template);
  });

  it('leaves a template with no stylesheet link unchanged', () => {
    const bare = '<head></head>';
    expect(inlineStylesheet(bare, () => 'x')).toBe(bare);
  });
});
