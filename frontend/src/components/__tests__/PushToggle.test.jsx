import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import PushToggle from '../PushToggle';
import { usePush } from '../../context/PushContext';

vi.mock('../../context/PushContext', () => ({ usePush: vi.fn() }));

const push = (status, extra = {}) => {
  const value = {
    status,
    busy: false,
    error: null,
    dismissed: false,
    turnOn: vi.fn(),
    turnOff: vi.fn(),
    dismiss: vi.fn(),
    ...extra,
  };
  usePush.mockReturnValue(value);
  return value;
};

describe('PushToggle', () => {
  it('shows nothing where notifications are unavailable', () => {
    push('unavailable');
    const { container } = render(<PushToggle />);
    expect(container).toBeEmptyDOMElement();
  });

  it('offers a button to enable them, from the panel', async () => {
    const { turnOn } = push('off');
    render(<PushToggle />);
    await userEvent.click(screen.getByRole('button', { name: 'Enable browser notifications' }));
    expect(turnOn).toHaveBeenCalledWith({ fromPanel: true });
  });

  it('dismisses the offer with its ×, and stays away once dismissed', async () => {
    const { dismiss } = push('off');
    const { rerender, container } = render(<PushToggle />);
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss notifications offer' }));
    expect(dismiss).toHaveBeenCalled();
    push('off', { dismissed: true });
    rerender(<PushToggle />);
    expect(container).toBeEmptyDOMElement();
  });

  it('says quietly when they are on, with a way to turn them off', async () => {
    const { turnOff } = push('on', { dismissed: true });
    render(<PushToggle />);
    expect(screen.getByText('Browser notifications are on.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Turn off' }));
    expect(turnOff).toHaveBeenCalled();
  });

  it('shows nothing when blocked, unless the button was just refused', () => {
    push('blocked');
    const { container, rerender } = render(<PushToggle />);
    expect(container).toBeEmptyDOMElement();
    push('blocked', { error: 'Notifications are blocked for mergers.fyi in this browser.' });
    rerender(<PushToggle />);
    expect(screen.getByRole('alert')).toHaveTextContent('blocked');
  });

  it('points iPhone and iPad users at the Home Screen, until dismissed', () => {
    push('home-screen');
    render(<PushToggle />);
    expect(screen.getByText(/add mergers.fyi to your Home Screen/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Dismiss notifications offer' })).toBeInTheDocument();
  });
});
