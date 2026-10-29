/* global process */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  extensionBusinessDays,
  extensionPhaseLabel,
  extensionReason,
  getTimelineExtensions,
  isExtensionTitle,
  PUBLIC_BENEFIT,
} from '../timelineExtensions';

// Golden fixture shared with scripts/tests/test_extension_titles.py — the
// single source of truth pinning these title rules to the pipeline's copy in
// scripts/generate/static_data/outputs/extensions.py. Read via node fs (Vitest
// runs with the frontend project dir as cwd, so the repo root is one level up),
// matching industryDivision.test.js.
const repoRoot = resolve(process.cwd(), '..');
const { cases } = JSON.parse(
  readFileSync(resolve(repoRoot, 'fixtures', 'extension-title-cases.json'), 'utf8'),
);
const extensionCases = cases.filter((c) => c.is_extension);

describe('extension title rules', () => {
  it('has golden cases on both sides of the rule', () => {
    expect(extensionCases.length).toBeGreaterThan(0);
    expect(extensionCases.length).toBeLessThan(cases.length);
  });

  it.each(cases)('reads "$title" as an extension: $is_extension', ({ title, is_extension }) => {
    expect(isExtensionTitle(title)).toBe(is_extension);
  });

  it.each(extensionCases)('parses "$title"', ({ title, business_days, reason }) => {
    expect(extensionBusinessDays(title)).toBe(business_days);
    expect(extensionReason(title)).toBe(reason);
  });

  it('treats a missing title as no extension', () => {
    expect(isExtensionTitle(undefined)).toBe(false);
  });
});

describe('getTimelineExtensions', () => {
  it('stacks phase 1 extensions after the 30-business-day window, matching the register deadline', () => {
    // MN-90008: three phase 1 extensions; the register's deadline is 17 Aug 2026.
    const result = getTimelineExtensions({
      effective_notification_datetime: '2026-05-21T12:00:00Z',
      end_of_determination_period: '2026-08-17T12:00:00Z',
      phase_1_determination_date: '2026-08-11T12:00:00Z',
      events: [
        { date: '2026-07-10T12:00:00Z', title: 'Timeline extended by 15 business days - following remedy offered by parties' },
        { date: '2026-06-19T12:00:00Z', title: 'Timeline extended by 10 business days - following request by parties' },
        { date: '2026-07-03T12:00:00Z', title: 'Timeline extended by 5 business days - following request by parties' },
        { date: '2026-05-21T12:00:00Z', title: 'Merger notified to ACCC' },
      ],
    });

    expect(result.map((e) => e.businessDays)).toEqual([10, 5, 15]);
    expect(result.every((e) => e.phase === 1)).toBe(true);
    expect(result[0].from).toBe('2026-07-06');
    expect(result[0].to).toBe(result[1].from);
    expect(result[1].to).toBe(result[2].from);
    expect(result[2].to).toBe('2026-08-17');
    expect(result[2].reason).toBe('remedy offered by parties');
  });

  it('anchors phase 2 extensions 90 business days on from the extended phase 1 deadline', () => {
    // MN-05013: one phase 1 extension, two phase 2 extensions the same day.
    const result = getTimelineExtensions({
      effective_notification_datetime: '2026-05-12T12:00:00Z',
      end_of_determination_period: '2026-12-17T12:00:00Z',
      phase_1_determination: 'Referred to phase 2',
      phase_1_determination_date: '2026-07-17T12:00:00Z',
      stage: 'Phase 2 - detailed assessment',
      events: [
        { date: '2026-06-15T12:00:00Z', title: 'Timeline extended by 20 business days – following request by notifying party' },
        { date: '2026-10-12T12:00:00Z', title: 'Timeline extended by 5 business days – following request by parties' },
        { date: '2026-10-12T12:00:00Z', title: 'Timeline extended by 9 business days – following request for further information' },
      ],
    });

    expect(result.map((e) => [e.phase, e.businessDays])).toEqual([[1, 20], [2, 5], [2, 9]]);
    expect(result[0].to).toBe('2026-07-23');
    expect(result[2].to).toBe('2026-12-17');
  });

  it('places nothing when a day count is missing', () => {
    expect(getTimelineExtensions({
      effective_notification_datetime: '2025-10-10T12:00:00Z',
      events: [{ date: '2025-11-06T12:00:00Z', title: 'ACCC decided to extend the Phase 1 determination period following receipt of extension request' }],
    })).toEqual([]);
  });

  it('anchors public benefit extensions 50 business days on from the application', () => {
    // MN-65005: the register's deadline moved from 22 Dec 2026 to 1 Feb 2027.
    const result = getTimelineExtensions({
      effective_notification_datetime: '2026-02-10T12:00:00Z',
      end_of_determination_period: '2027-02-01T12:00:00Z',
      phase_1_determination: 'Referred to phase 2',
      phase_1_determination_date: '2026-03-24T12:00:00Z',
      phase_2_determination_date: '2026-09-22T12:00:00Z',
      public_benefit_application_date: '2026-10-13T12:00:00Z',
      stage: 'Public benefit phase',
      events: [
        { date: '2026-10-29T12:00:00Z', title: 'Timeline extended by 15 business days – following remedy offered by parties' },
      ],
    });

    expect(result).toEqual([{
      date: '2026-10-29T12:00:00Z',
      businessDays: 15,
      reason: 'remedy offered by parties',
      phase: PUBLIC_BENEFIT,
      from: '2026-12-22',
      to: '2027-02-01',
    }]);
    expect(extensionPhaseLabel(PUBLIC_BENEFIT)).toBe('Public benefit phase');
    expect(extensionPhaseLabel(2)).toBe('Phase 2');
  });

  it('skips extensions granted after the phase 2 determination with no public benefit application', () => {
    expect(getTimelineExtensions({
      effective_notification_datetime: '2026-03-03T12:00:00Z',
      phase_1_determination: 'Referred to phase 2',
      phase_1_determination_date: '2026-04-16T12:00:00Z',
      phase_2_determination_date: '2026-09-23T12:00:00Z',
      events: [{ date: '2026-10-01T12:00:00Z', title: 'Timeline extended by 10 business days' }],
    })).toEqual([]);
  });

  it('returns nothing for waivers or matters without extensions', () => {
    expect(getTimelineExtensions({ effective_notification_datetime: '2026-05-21T12:00:00Z', events: [] })).toEqual([]);
    expect(getTimelineExtensions({ is_waiver: true, effective_notification_datetime: '2026-05-21T12:00:00Z' })).toEqual([]);
  });
});
