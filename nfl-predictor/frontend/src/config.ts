/**
 * Centralized season configuration — single source of truth for year values.
 *
 * Replaces hardcoded 2024/2025 literals scattered across the app so the UI rolls
 * forward automatically instead of going stale each NFL season.
 *
 * NFL season labelling: a season runs Sep–early Feb and is named for the year it
 * starts in. So Jan–Aug belongs to the *previous* season label.
 */

export const FIRST_SEASON = 1990;

/** The current NFL season label, derived from today's date. */
export function currentNflSeason(now: Date = new Date()): number {
  const year = now.getFullYear();
  const month = now.getMonth(); // 0 = Jan … 8 = Sep
  return month >= 8 ? year : year - 1;
}

/** Current season (upcoming games, schedule, live accuracy). */
export const CURRENT_SEASON = currentNflSeason();

/**
 * Last season with complete played data — used for fantasy leaderboards, draft
 * rankings, trade values, etc. that need a fully-played season of stats.
 */
export const LAST_COMPLETED_SEASON = CURRENT_SEASON - 1;

export const SEASON_COUNT = CURRENT_SEASON - FIRST_SEASON + 1;

/** e.g. "1990–2025" */
export const SEASON_RANGE_LABEL = `${FIRST_SEASON}–${CURRENT_SEASON}`;

/** Comma-separated recent seasons for backtest accuracy (last two). */
export const ACCURACY_SEASONS = `${CURRENT_SEASON - 1},${CURRENT_SEASON}`;

/** All seasons, newest first — for dropdowns. */
export const ALL_SEASONS: number[] = Array.from(
  { length: SEASON_COUNT },
  (_, i) => CURRENT_SEASON - i,
);

/** Recent N seasons, newest first — for compact selectors. */
export function recentSeasons(n: number): number[] {
  return Array.from({ length: n }, (_, i) => CURRENT_SEASON - i);
}
