import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import Digest from '../Digest';
import { dataCache } from '../../utils/dataCache';

function ok(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
}

// MN-65005's shape: refused at Phase 2, then the parties applied for a public
// benefit determination, which put the matter back under assessment.
const TO_PUBLIC_BENEFIT = {
  merger_id: 'MN-65005',
  merger_name: 'Insurance Australia Group – RAC Insurance',
  stage: 'Public benefit phase',
  phase_2_determination: 'Not approved',
  public_benefit_application_date: '2026-10-13T12:00:00Z',
  events: [],
};

function digest(overrides = {}) {
  return {
    period_start: '2026-10-12T00:00:00+11:00',
    period_end: '2026-10-18T23:59:59+11:00',
    new_deals_notified: [],
    deals_cleared: [],
    deals_referred_to_phase_2: [],
    deals_to_public_benefit: [],
    deals_declined: [],
    deals_assessment_ceased: [],
    deals_appealed_to_tribunal: [],
    ongoing_phase_1: [],
    ongoing_phase_2: [],
    ongoing_public_benefit: [],
    ongoing_tribunal_appeals: [],
    ...overrides,
  };
}

function renderPage(data) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.resolve(ok(data)));
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <Digest />
      </MemoryRouter>
    </HelmetProvider>
  );
}

describe('Digest', () => {
  beforeEach(() => {
    dataCache.clear();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    dataCache.clear();
  });

  it('lists a move to the public benefit phase with its own chip and section', async () => {
    renderPage(digest({ deals_to_public_benefit: [TO_PUBLIC_BENEFIT] }));

    expect(await screen.findByText('To public benefit phase')).toBeInTheDocument();
    const section = document.getElementById('mergers-to-public-benefit');
    expect(section).not.toBeNull();
    expect(section).toHaveTextContent('Mergers moved to the public benefit phase');
    expect(section).toHaveTextContent('Insurance Australia Group – RAC Insurance');
    expect(section).toHaveTextContent('13/10/2026');
    expect(section).toHaveTextContent('Not approved');
  });

  it('shows neither in a week without one, or for a digest that predates the field', async () => {
    const { deals_to_public_benefit: _omitted, ...older } = digest();
    renderPage(older);

    expect(await screen.findByText('Catch me up')).toBeInTheDocument();
    expect(screen.queryByText('To public benefit phase')).not.toBeInTheDocument();
    expect(document.getElementById('mergers-to-public-benefit')).toBeNull();
  });
});
