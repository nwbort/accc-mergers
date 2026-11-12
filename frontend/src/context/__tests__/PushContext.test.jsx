import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TrackingProvider } from '../TrackingContext';
import { PushProvider } from '../PushContext';
import * as webPush from '../../push/webPush';

vi.mock('../../push/webPush', () => ({
  disablePush: vi.fn(async () => {}),
  enablePush: vi.fn(),
  needsHomeScreen: vi.fn(() => false),
  pushConfigured: vi.fn(() => true),
  pushEnabled: vi.fn(),
  pushPermission: vi.fn(),
  pushSupported: vi.fn(() => true),
  pushToken: vi.fn(async () => 'token'),
  syncTopics: vi.fn(async () => {}),
}));

const mount = () =>
  render(
    <TrackingProvider>
      <PushProvider>
        <div />
      </PushProvider>
    </TrackingProvider>,
  );

// There's no "turn off" on the site: blocking notifications in the browser is
// how, and the next visit deletes the token so Google drops its topics.
describe('PushProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn(async () => ({ ok: false, json: async () => null }));
  });

  it('deletes the token of a browser that had notifications on and now blocks them', () => {
    webPush.pushEnabled.mockReturnValue(true);
    webPush.pushPermission.mockReturnValue('denied');
    mount();
    expect(webPush.disablePush).toHaveBeenCalledTimes(1);
  });

  it('leaves a browser alone that still allows them, or never had them on', () => {
    webPush.pushEnabled.mockReturnValue(true);
    webPush.pushPermission.mockReturnValue('granted');
    mount();
    webPush.pushEnabled.mockReturnValue(false);
    webPush.pushPermission.mockReturnValue('denied');
    mount();
    expect(webPush.disablePush).not.toHaveBeenCalled();
  });
});
