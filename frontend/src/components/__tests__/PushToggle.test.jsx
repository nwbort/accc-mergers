import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import PushToggle from '../PushToggle';
import { usePush } from '../../context/PushContext';

vi.mock('../../context/PushContext', () => ({ usePush: vi.fn() }));

const push = (status, extra = {}) =>
  usePush.mockReturnValue({ status, busy: false, error: null, turnOn: vi.fn(), turnOff: vi.fn(), ...extra });

describe('PushToggle', () => {
  it('shows nothing where notifications are unavailable', () => {
    push('unavailable');
    const { container } = render(<PushToggle />);
    expect(container).toBeEmptyDOMElement();
  });

  it('turns notifications on from the switch', async () => {
    const turnOn = vi.fn();
    push('off', { turnOn });
    render(<PushToggle />);
    const toggle = screen.getByRole('switch', { name: 'Browser notifications' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    await userEvent.click(toggle);
    expect(turnOn).toHaveBeenCalled();
  });

  it('turns them off again', async () => {
    const turnOff = vi.fn();
    push('on', { turnOff });
    render(<PushToggle />);
    await userEvent.click(screen.getByRole('switch', { name: 'Browser notifications' }));
    expect(turnOff).toHaveBeenCalled();
  });

  it('says following still works when the browser blocks notifications', () => {
    push('blocked');
    render(<PushToggle />);
    expect(screen.queryByRole('switch')).toBeNull();
    expect(screen.getByText(/Following still works/)).toBeInTheDocument();
  });

  it('points iPhone and iPad users at the Home Screen', () => {
    push('home-screen');
    render(<PushToggle />);
    expect(screen.getByText(/add mergers.fyi to your Home Screen/)).toBeInTheDocument();
  });
});
