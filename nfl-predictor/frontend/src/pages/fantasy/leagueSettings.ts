// League settings (scoring format + league size) shared by all fantasy tabs
// and the draft board. Persisted in localStorage; mirrors the backend
// LeagueSettings defaults (fantasy.nfl.com: Standard scoring, 10 teams).

import { useCallback, useSyncExternalStore } from 'react';

export type Scoring = 'standard' | 'ppr' | 'half_ppr';

export interface LeagueSettings {
  scoring: Scoring;
  leagueSize: number; // 8-20
}

export const NFL_DEFAULT_SLOTS: Record<string, number> = {
  QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DST: 1, BN: 7,
};

export const DEFAULT_LEAGUE_SETTINGS: LeagueSettings = {
  scoring: 'standard',
  leagueSize: 10,
};

const STORAGE_KEY = 'nfl-predictor.leagueSettings';
const CHANGE_EVENT = 'nfl-predictor:league-settings-changed';

const VALID_SCORING: Scoring[] = ['standard', 'ppr', 'half_ppr'];

export function loadLeagueSettings(): LeagueSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_LEAGUE_SETTINGS };
    const parsed = JSON.parse(raw) as Partial<LeagueSettings>;
    const scoring = VALID_SCORING.includes(parsed.scoring as Scoring)
      ? (parsed.scoring as Scoring)
      : DEFAULT_LEAGUE_SETTINGS.scoring;
    const size = typeof parsed.leagueSize === 'number'
      && parsed.leagueSize >= 8 && parsed.leagueSize <= 20
      ? parsed.leagueSize
      : DEFAULT_LEAGUE_SETTINGS.leagueSize;
    return { scoring, leagueSize: size };
  } catch {
    return { ...DEFAULT_LEAGUE_SETTINGS };
  }
}

export function saveLeagueSettings(settings: LeagueSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

// ── React hook (stays in sync across components via a window event) ─────────

let cached: { raw: string | null; value: LeagueSettings } | null = null;

function getSnapshot(): LeagueSettings {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!cached || cached.raw !== raw) {
    cached = { raw, value: loadLeagueSettings() };
  }
  return cached.value;
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener('storage', onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener('storage', onChange);
  };
}

export function useLeagueSettings(): [LeagueSettings, (s: LeagueSettings) => void] {
  const settings = useSyncExternalStore(subscribe, getSnapshot);
  const update = useCallback((s: LeagueSettings) => saveLeagueSettings(s), []);
  return [settings, update];
}
