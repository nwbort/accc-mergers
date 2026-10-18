import { describe, it, expect } from 'vitest';
import { eventAnchorId } from '../eventAnchor';

describe('eventAnchorId', () => {
  it('combines the calendar date with a slug of the title', () => {
    expect(eventAnchorId({ date: '2026-03-04T12:00:00Z', title: 'Merger notified to ACCC' }))
      .toBe('event-2026-03-04-merger-notified-to-accc');
  });

  it('prefers display_title, as the detail page renders it', () => {
    expect(eventAnchorId({ date: '2026-03-04', title: 'raw', display_title: 'Shown title' }))
      .toBe('event-2026-03-04-shown-title');
  });

  it('agrees for the same event whichever date form it carries', () => {
    const a = eventAnchorId({ date: '2026-03-04', title: 'X' });
    const b = eventAnchorId({ date: '2026-03-04T12:00:00Z', title: 'X' });
    expect(a).toBe(b);
  });
});
