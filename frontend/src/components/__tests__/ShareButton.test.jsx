import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ShareButton from '../ShareButton';

const PATH = '/mergers/MN-01016/acme-bidco';
const URL_ = `https://mergers.fyi${PATH}`;

function setClipboard(writeText) {
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
}

describe('ShareButton', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete navigator.share;
  });

  it('opens a menu with the link and share targets', () => {
    render(<ShareButton path={PATH} title="Acme / Bidco" />);
    const button = screen.getByRole('button', { name: 'Share this page' });
    expect(button).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    const dialog = screen.getByRole('dialog', { name: 'Share this page' });
    expect(screen.getByLabelText('Link to this page')).toHaveValue(URL_);
    for (const name of [/LinkedIn/, /Bluesky/, /^X/, /Email/]) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument();
    }
    // Focus moves into the menu so the portal doesn't strand keyboard users.
    expect(dialog).toContainElement(document.activeElement);
  });

  it('copies the canonical link and says so', async () => {
    const writeText = vi.fn().mockResolvedValue();
    setClipboard(writeText);
    render(<ShareButton path={PATH} title="Acme / Bidco" />);
    fireEvent.click(screen.getByRole('button', { name: 'Share this page' }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Copy link' }));
    });
    expect(writeText).toHaveBeenCalledWith(URL_);
    expect(screen.getByRole('button', { name: 'Link copied' })).toBeInTheDocument();
  });

  it('closes on Escape and returns focus to the button', () => {
    render(<ShareButton path={PATH} title="Acme / Bidco" />);
    const button = screen.getByRole('button', { name: 'Share this page' });
    fireEvent.click(button);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(button).toHaveFocus();
  });

  it('hands off to the share sheet on a touch device', async () => {
    const share = vi.fn().mockResolvedValue();
    navigator.share = share;
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    render(<ShareButton path={PATH} title="Acme / Bidco" />);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Share this page' }));
    });
    expect(share).toHaveBeenCalledWith({ title: 'Acme / Bidco', url: URL_ });
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
