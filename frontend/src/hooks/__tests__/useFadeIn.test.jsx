import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import NickTwort from '../../pages/NickTwort';
import PrivacyPolicy from '../../pages/PrivacyPolicy';
import Copyright from '../../pages/Copyright';
import { CommentaryList } from '../../pages/Commentary';
import { markAppSettled } from '../../utils/appMount';

// The pages whose prerendered HTML is drawn by their own components: on first
// load React mounts over identical content, so they mustn't fade in from
// transparent then; reached by navigating, they fade in as every page does.
const PAGES = {
  '/nick-twort': () => <NickTwort />,
  '/privacy': () => <PrivacyPolicy />,
  '/copyright': () => <Copyright />,
  '/commentary': () => <CommentaryList items={[]} />,
};

function fades(path) {
  const { container, unmount } = render(
    <HelmetProvider>
      <MemoryRouter initialEntries={[path]}>{PAGES[path]()}</MemoryRouter>
    </HelmetProvider>,
  );
  const faded = !!container.querySelector('.animate-fade-in');
  unmount();
  return faded;
}

describe('useFadeIn on pages prerendered from their own components', () => {
  it('skips the fade on first load, keeps it on navigation', () => {
    for (const path of Object.keys(PAGES)) expect(fades(path), `${path} first load`).toBe(false);
    markAppSettled(); // one-way, as in the app; this file's only test
    for (const path of Object.keys(PAGES)) expect(fades(path), `${path} navigated to`).toBe(true);
  });
});
