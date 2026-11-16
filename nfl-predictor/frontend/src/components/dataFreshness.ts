const DAY_MS = 24 * 60 * 60 * 1000;

interface Freshness {
  data_updated_at: string | null;
  last_scrape_at: string | null;
}

/**
 * Whether the footer should warn that the data is stale.
 *
 * Two independent clocks: `data_updated_at` (rosters/injuries) and
 * `last_scrape_at` (the weekly run that also brings game results). A
 * roster-only import moves the first without the second, so either one being
 * overdue is enough.
 */
export function isDataStale(h: Freshness, now: number = Date.now()): boolean {
  const older = (iso: string | null, days: number) =>
    iso !== null && now - new Date(iso.replace(' ', 'T')).getTime() > days * DAY_MS;
  return older(h.data_updated_at, 7) || older(h.last_scrape_at, 8);
}
