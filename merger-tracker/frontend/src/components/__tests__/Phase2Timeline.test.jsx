import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Phase2Timeline from '../Phase2Timeline';

const renderTimeline = (matters) =>
  render(
    <MemoryRouter>
      <Phase2Timeline matters={matters} />
    </MemoryRouter>
  );

const makeMatter = (overrides) => ({
  merger_id: 'MN-00001',
  merger_name: 'Acme – Globex',
  referral_date: '2026-01-01T12:00:00Z',
  nocc_date: '2026-02-10T12:00:00Z',
  nocc_issued: true,
  end_of_determination_period: '2026-06-01T12:00:00Z',
  determination: null,
  determination_date: null,
  ...overrides,
});

describe('Phase2Timeline', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-01T00:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders an empty state when there are no current matters', () => {
    renderTimeline([]);
    expect(screen.getByText('No matters are currently in Phase 2.')).toBeInTheDocument();
  });

  it('renders a bar per matter with referral, NOCC and determination milestones', () => {
    renderTimeline([makeMatter()]);
    expect(screen.getByText('Acme – Globex')).toBeInTheDocument();
    expect(screen.getByText('Referred')).toBeInTheDocument();
    expect(screen.getByText('01 Jan 2026')).toBeInTheDocument();
    expect(screen.getByText('NOCC issued 10 Feb 2026')).toBeInTheDocument();
    expect(screen.getByText('Determination due')).toBeInTheDocument();
    expect(screen.getByText('01 Jun 2026')).toBeInTheDocument();
  });

  it('labels a not-yet-issued NOCC as due, not issued', () => {
    renderTimeline([makeMatter({ nocc_issued: false })]);
    expect(screen.getByText('NOCC due 10 Feb 2026')).toBeInTheDocument();
  });

  it('omits the NOCC milestone line when no NOCC date is available', () => {
    renderTimeline([makeMatter({ nocc_date: null })]);
    expect(screen.queryByText(/NOCC/)).not.toBeInTheDocument();
  });
});
