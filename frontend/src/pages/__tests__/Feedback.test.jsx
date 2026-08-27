import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Feedback from '../Feedback';

const renderAt = (path) => render(
  <HelmetProvider>
    <MemoryRouter initialEntries={[path]}>
      <Feedback />
    </MemoryRouter>
  </HelmetProvider>
);

describe('Feedback', () => {
  beforeEach(() => {
    // The page renders a Turnstile widget on mount; stub it out so the form
    // itself is what's under test.
    window.turnstile = { render: vi.fn(() => 'widget'), remove: vi.fn(), reset: vi.fn() };
  });

  it('starts with an empty message box', () => {
    renderAt('/feedback');

    expect(screen.getByLabelText(/Message/)).toHaveValue('');
  });

  it('seeds the message box from the ?message= param', () => {
    renderAt('/feedback?message=MN-01050%20pre-notification%20estimate%20looks%20wrong.%20It%20should%20be%20');

    const box = screen.getByLabelText(/Message/);
    expect(box).toHaveValue('MN-01050 pre-notification estimate looks wrong. It should be ');
    // Focused with the caret at the end, ready to be finished rather than edited.
    expect(box).toHaveFocus();
    expect(box.selectionStart).toBe(box.value.length);
  });

  it('caps a seeded message at what the box itself accepts', () => {
    renderAt(`/feedback?message=${'x'.repeat(6000)}`);

    expect(screen.getByLabelText(/Message/)).toHaveValue('x'.repeat(5000));
  });
});
