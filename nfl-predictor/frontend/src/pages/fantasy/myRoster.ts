// My-roster persistence: player ids imported via RosterImportHelper survive
// page reloads and feed the Waiver (exclusion) and Optimizer tabs.

const keyFor = (season: number) => `nfl-predictor.myRoster.${season}`;

export function loadMyRoster(season: number): number[] {
  try {
    const raw = localStorage.getItem(keyFor(season));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((n) => typeof n === 'number') : [];
  } catch {
    return [];
  }
}

export function saveMyRoster(season: number, ids: number[]): void {
  localStorage.setItem(keyFor(season), JSON.stringify(ids));
}

export function clearMyRoster(season: number): void {
  localStorage.removeItem(keyFor(season));
}
