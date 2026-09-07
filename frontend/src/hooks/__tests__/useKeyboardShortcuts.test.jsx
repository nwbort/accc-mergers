import { act, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { useKeyboardShortcuts } from '../useKeyboardShortcuts';
import KeyboardShortcutsHelp from '../../components/KeyboardShortcutsHelp';
import { SHORTCUT_PAGES } from '../../constants/navPages';

// The hook navigates, so it needs a router around it. This harness renders the
// current path so a test can assert where a chord landed.
function Harness() {
  useKeyboardShortcuts();
  const location = useLocation();
  return <p>path: {location.pathname}</p>;
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="*" element={<Harness />} />
      </Routes>
    </MemoryRouter>
  );
}

/** Press a bare key on document.body, the way a reader not in an input would. */
function press(key) {
  act(() => {
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
  });
}

describe('useKeyboardShortcuts', () => {
  // Driven from the shared table rather than a list repeated here: a chord
  // added to navPages.js is covered the moment it is declared.
  it.each(SHORTCUT_PAGES.map(({ label, shortcut, path }) => [label, shortcut, path]))(
    'sends "g" then "%s" (%s) to %s',
    (_label, shortcut, path) => {
      // Start somewhere that is not the destination, so a passing assertion
      // means the chord navigated rather than that we never left.
      renderAt('/nick-twort');

      press('g');
      press(shortcut);

      expect(screen.getByText(`path: ${path}`)).toBeInTheDocument();
    }
  );

  it('ignores a chord key on its own, so typing outside an input cannot navigate', () => {
    renderAt('/');

    press('s');

    expect(screen.getByText('path: /')).toBeInTheDocument();
  });

  it('forgets the "g" prefix after an unbound second key', () => {
    renderAt('/');

    press('g');
    press('z');
    press('s');

    expect(screen.getByText('path: /')).toBeInTheDocument();
  });
});

describe('KeyboardShortcutsHelp', () => {
  // The overlay and the hook read the same table, so this pins that they stay
  // in step: every working chord is documented, and nothing is documented that
  // does not work.
  it('documents every chord the hook handles, and only those', () => {
    render(<KeyboardShortcutsHelp isOpen onClose={() => {}} />);

    const goRows = screen
      .getAllByRole('listitem')
      .filter((row) => row.textContent.startsWith('Go to '));

    expect(goRows).toHaveLength(SHORTCUT_PAGES.length);

    for (const { label, shortcut } of SHORTCUT_PAGES) {
      const row = screen.getByText(`Go to ${label}`).closest('li');
      // The <kbd> elements are the keys themselves; the "then" between them is
      // a separator, not a key.
      const keys = [...row.querySelectorAll('kbd')].map((el) => el.textContent);
      expect(keys).toEqual(['g', shortcut]);
    }
  });
});
