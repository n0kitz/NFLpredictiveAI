import { describe, it, expect } from 'vitest';
import { isDataStale } from './dataFreshness';

const NOW = new Date('2026-11-14T12:00:00Z').getTime();

describe('isDataStale', () => {
  it('is fresh when rosters and the last run are recent', () => {
    expect(isDataStale({ data_updated_at: '2026-11-12', last_scrape_at: '2026-11-11 06:00:00' }, NOW)).toBe(false);
  });

  it('flags roster/injury data older than a week', () => {
    expect(isDataStale({ data_updated_at: '2026-08-22', last_scrape_at: null }, NOW)).toBe(true);
  });

  it('flags a weekly run that is overdue even if rosters look fresh', () => {
    // A roster-only import refreshes data_updated_at without touching results.
    expect(isDataStale({ data_updated_at: '2026-11-13', last_scrape_at: '2026-10-28 06:00:00' }, NOW)).toBe(true);
  });

  it('says nothing when there is no timestamp at all', () => {
    expect(isDataStale({ data_updated_at: null, last_scrape_at: null }, NOW)).toBe(false);
  });
});
