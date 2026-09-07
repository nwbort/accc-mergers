import { act, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { useKeyboardShortcuts } from '../useKeyboardShortcuts';
import KeyboardShortcutsHelp from '../../components/KeyboardShortcutsHelp';

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
  it('sends "g" then "s" to the current status page', () => {
    renderAt('/');

    press('g');
    press('s');

    expect(screen.getByText('path: /current-status')).toBeInTheDocument();
  });

  it('ignores "s" on its own, so typing outside an input cannot navigate', () => {
    renderAt('/');

    press('s');

    expect(screen.getByText('path: /')).toBeInTheDocument();
  });

  it('lists the chord in the help overlay, so it is discoverable', () => {
    render(<KeyboardShortcutsHelp isOpen onClose={() => {}} />);

    const row = screen.getByText('Go to Current status').closest('li');
    expect(row).toHaveTextContent('g');
    expect(row).toHaveTextContent('then');
    expect(row).toHaveTextContent('s');
  });
});
