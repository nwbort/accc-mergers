import { StrictMode, useEffect } from 'react';
import { act, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useNavigate } from 'react-router';
import ScrollToTop from '../ScrollToTop';

// Hands the router's navigate function out to the test.
const router = {};
function Nav() {
  const go = useNavigate();
  useEffect(() => {
    router.navigate = go;
  });
  return null;
}

function mount(path) {
  const scroll = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  render(
    <StrictMode>
      <MemoryRouter initialEntries={[path]}>
        <ScrollToTop />
        <Nav />
      </MemoryRouter>
    </StrictMode>,
  );
  return scroll;
}

describe('ScrollToTop', () => {
  afterEach(() => vi.restoreAllMocks());

  // React can mount seconds after a prerendered page appears (main.jsx), and
  // must not yank a reader who has started scrolling it back to the top.
  it('leaves the page where it is when the app mounts, StrictMode and all', () => {
    expect(mount('/mergers')).not.toHaveBeenCalled();
  });

  it('scrolls to the top on navigating to another page', () => {
    const scroll = mount('/mergers');
    act(() => router.navigate('/phase-2'));
    expect(scroll).toHaveBeenCalledWith(0, 0);
  });

  it('leaves a link to a point on a page to the page', () => {
    const scroll = mount('/mergers');
    act(() => router.navigate('/mergers/MN-01016#event-x'));
    expect(scroll).not.toHaveBeenCalled();
  });
});
