import { describe, expect, it } from 'vitest';
import { isAppKey } from '../appKeys';

const key = (k, mods = {}) => ({ key: k, ...mods });

describe('isAppKey', () => {
  it('starts the app on shortcuts and typing', () => {
    for (const k of ['/', 'g', 'k', 'a', 'Enter', 'Escape', '?']) expect(isAppKey(key(k)), k).toBe(true);
    expect(isAppKey(key('k', { ctrlKey: true })), 'Ctrl+K').toBe(true);
    expect(isAppKey(key('k', { metaKey: true })), 'Cmd+K').toBe(true);
  });

  it('leaves the static page up for keys that only read it', () => {
    for (const k of ['ArrowDown', 'ArrowUp', ' ', 'PageDown', 'PageUp', 'Home', 'End', 'Tab', 'Shift', 'Control', 'Meta', 'Alt']) {
      expect(isAppKey(key(k)), JSON.stringify(k)).toBe(false);
    }
  });

  it('leaves it up for Ctrl/Cmd combinations other than the palette', () => {
    for (const k of ['c', 'a', 'f', 'p', '+', '0']) {
      expect(isAppKey(key(k, { ctrlKey: true })), `Ctrl+${k}`).toBe(false);
      expect(isAppKey(key(k, { metaKey: true })), `Cmd+${k}`).toBe(false);
    }
    expect(isAppKey(key('K', { ctrlKey: true, shiftKey: true })), 'Ctrl+Shift+K').toBe(true);
  });
});
