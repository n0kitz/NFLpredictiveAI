import { useState, useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from 'recharts';
import { api } from '../api/client';
import type { PlayerProfile, PlayerSearchResult, PlayerWeekCell, PlayerStatsEntry } from '../api/types';
import Spinner from '../components/Spinner';
import { getTeamColors } from '../theme/teamColors';
import { LAST_COMPLETED_SEASON, recentSeasons } from '../config';

const SEASON_OPTIONS = recentSeasons(8).filter((s) => s <= LAST_COMPLETED_SEASON);

const tooltipStyle = {
  backgroundColor: 'var(--color-surface-800)',
  border: '1px solid var(--color-border)',
  borderRadius: '6px',
  fontSize: '12px',
};

// ── Debounced player search box ───────────────────────────────────────────────

function PlayerSearchBox({ label, onSelect }: {
  label: string;
  onSelect: (p: PlayerSearchResult) => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PlayerSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    timer.current = setTimeout(() => {
      api.searchPlayers(query.trim())
        .then((r) => { setResults(r.slice(0, 8)); setOpen(true); })
        .catch(() => setResults([]));
    }, 250);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [query]);

  return (
    <div className="relative flex-1">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={label}
        aria-label={label}
        className="w-full bg-surface-800 border border-border rounded-md px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
      />
      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full bg-surface-800 border border-border rounded-md overflow-hidden shadow-xl" role="listbox">
          {results.map((r) => (
            <li key={r.player_id} role="option" aria-selected="false">
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-surface-700 transition-colors flex items-center gap-2"
                onMouseDown={() => { onSelect(r); setQuery(''); setOpen(false); }}
              >
                {r.headshot_url && (
                  <img src={r.headshot_url} alt="" className="w-6 h-6 rounded-full object-cover bg-surface-700" />
                )}
                <span className="text-text-primary">{r.full_name}</span>
                <span className="text-text-muted text-xs ml-auto">{r.position ?? ''} {r.team_abbr ?? ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Stat comparison rows ──────────────────────────────────────────────────────

type StatRow = { label: string; get: (s: PlayerStatsEntry) => string; raw: (s: PlayerStatsEntry) => number };

function rowsForPosition(pos: string): StatRow[] {
  const base: StatRow[] = [
    { label: 'Games', get: (s) => String(s.games_played), raw: (s) => s.games_played },
    { label: 'Fantasy PPR', get: (s) => s.fantasy_points_ppr.toFixed(1), raw: (s) => s.fantasy_points_ppr },
  ];
  if (pos === 'QB') {
    return [
      ...base,
      { label: 'Pass Yards', get: (s) => s.pass_yards.toLocaleString(), raw: (s) => s.pass_yards },
      { label: 'Pass TD', get: (s) => String(s.pass_tds), raw: (s) => s.pass_tds },
      { label: 'INT', get: (s) => String(s.interceptions), raw: (s) => -s.interceptions },
      { label: 'Passer Rating', get: (s) => s.passer_rating.toFixed(1), raw: (s) => s.passer_rating },
      { label: 'Rush Yards', get: (s) => String(s.rush_yards), raw: (s) => s.rush_yards },
    ];
  }
  if (pos === 'RB' || pos === 'FB') {
    return [
      ...base,
      { label: 'Carries', get: (s) => String(s.rush_attempts), raw: (s) => s.rush_attempts },
      { label: 'Rush Yards', get: (s) => s.rush_yards.toLocaleString(), raw: (s) => s.rush_yards },
      { label: 'Yards/Carry', get: (s) => s.yards_per_carry.toFixed(1), raw: (s) => s.yards_per_carry },
      { label: 'Rush TD', get: (s) => String(s.rush_tds), raw: (s) => s.rush_tds },
      { label: 'Receptions', get: (s) => String(s.receptions), raw: (s) => s.receptions },
      { label: 'Rec Yards', get: (s) => String(s.rec_yards), raw: (s) => s.rec_yards },
    ];
  }
  if (pos === 'WR' || pos === 'TE') {
    return [
      ...base,
      { label: 'Targets', get: (s) => String(s.targets), raw: (s) => s.targets },
      { label: 'Receptions', get: (s) => String(s.receptions), raw: (s) => s.receptions },
      { label: 'Rec Yards', get: (s) => s.rec_yards.toLocaleString(), raw: (s) => s.rec_yards },
      { label: 'Yards/Rec', get: (s) => s.yards_per_reception.toFixed(1), raw: (s) => s.yards_per_reception },
      { label: 'Rec TD', get: (s) => String(s.rec_tds), raw: (s) => s.rec_tds },
    ];
  }
  return [
    ...base,
    { label: 'Tackles', get: (s) => String(s.tackles), raw: (s) => s.tackles },
    { label: 'Sacks', get: (s) => s.sacks.toFixed(1), raw: (s) => s.sacks },
    { label: 'Def INT', get: (s) => String(s.interceptions_def), raw: (s) => s.interceptions_def },
  ];
}

// ── Player column header ──────────────────────────────────────────────────────

function PlayerHeader({ player, color, onClear }: {
  player: PlayerProfile; color: string; onClear: () => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <div
        className="w-12 h-12 rounded-lg overflow-hidden flex items-center justify-center shrink-0"
        style={{ backgroundColor: `${color}22` }}
      >
        {player.headshot_url
          ? <img src={player.headshot_url} alt={player.full_name} className="w-full h-full object-cover" />
          : <span className="font-display font-bold text-text-muted">{player.position ?? '?'}</span>}
      </div>
      <div className="min-w-0">
        <Link to={`/players/${player.player_id}`} className="font-display font-bold text-text-primary hover:text-accent transition-colors block truncate">
          {player.full_name}
        </Link>
        <span className="text-xs text-text-muted">
          {player.position ?? '—'}{player.team_abbr ? ` · ${player.team_abbr}` : ''}
        </span>
      </div>
      <button
        onClick={onClear}
        aria-label={`Remove ${player.full_name}`}
        className="ml-auto text-text-muted hover:text-loss text-lg leading-none px-1"
      >
        ×
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PlayerCompare() {
  const [params, setParams] = useSearchParams();
  const idA = params.get('a') ? Number(params.get('a')) : null;
  const idB = params.get('b') ? Number(params.get('b')) : null;

  const [playerA, setPlayerA] = useState<PlayerProfile | null>(null);
  const [playerB, setPlayerB] = useState<PlayerProfile | null>(null);
  const [season, setSeason] = useState(SEASON_OPTIONS[0]);
  const [weeksA, setWeeksA] = useState<PlayerWeekCell[]>([]);
  const [weeksB, setWeeksB] = useState<PlayerWeekCell[]>([]);
  const [loading, setLoading] = useState(false);

  const setId = (key: 'a' | 'b', id: number | null) => {
    const next = new URLSearchParams(params);
    if (id === null) next.delete(key);
    else next.set(key, String(id));
    setParams(next, { replace: true });
  };

  useEffect(() => {
    let cancelled = false;
    if (idA === null || Number.isNaN(idA)) { setPlayerA(null); return; }
    api.getPlayer(idA).then((p) => { if (!cancelled) setPlayerA(p); }).catch(() => setPlayerA(null));
    return () => { cancelled = true; };
  }, [idA]);

  useEffect(() => {
    let cancelled = false;
    if (idB === null || Number.isNaN(idB)) { setPlayerB(null); return; }
    api.getPlayer(idB).then((p) => { if (!cancelled) setPlayerB(p); }).catch(() => setPlayerB(null));
    return () => { cancelled = true; };
  }, [idB]);

  useEffect(() => {
    let cancelled = false;
    if (!playerA || !playerB) return;
    setLoading(true);
    Promise.all([
      api.getPlayerWeeklyStats(playerA.player_id, season).catch(() => null),
      api.getPlayerWeeklyStats(playerB.player_id, season).catch(() => null),
    ]).then(([a, b]) => {
      if (cancelled) return;
      setWeeksA(a?.weeks ?? []);
      setWeeksB(b?.weeks ?? []);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [playerA, playerB, season]);

  const colorA = playerA?.team_abbr ? getTeamColors(playerA.team_abbr).primary : 'var(--color-accent)';
  let colorB = playerB?.team_abbr ? getTeamColors(playerB.team_abbr).primary : '#60a5fa';
  if (playerA?.team_abbr && playerA.team_abbr === playerB?.team_abbr) {
    colorB = getTeamColors(playerB.team_abbr!).secondary;
  }

  const chartData = (() => {
    const byWeek = new Map<number, { week: number; a: number | null; b: number | null }>();
    for (const c of weeksA) {
      if (c.fantasy_points_ppr !== 0 || c.snap_pct > 0) {
        byWeek.set(c.week, { week: c.week, a: Math.round(c.fantasy_points_ppr * 10) / 10, b: null });
      }
    }
    for (const c of weeksB) {
      if (c.fantasy_points_ppr !== 0 || c.snap_pct > 0) {
        const row = byWeek.get(c.week) ?? { week: c.week, a: null, b: null };
        row.b = Math.round(c.fantasy_points_ppr * 10) / 10;
        byWeek.set(c.week, row);
      }
    }
    return Array.from(byWeek.values()).sort((x, y) => x.week - y.week);
  })();

  const rows = playerA ? rowsForPosition((playerA.position ?? '').toUpperCase()) : [];

  return (
    <div className="max-w-3xl mx-auto animate-fade-up">
      <div className="mb-6">
        <div className="font-display text-[11px] font-bold tracking-[0.2em] uppercase text-accent">
          Head to head
        </div>
        <h1 className="font-display text-2xl font-bold text-text-primary uppercase tracking-tight">
          Compare Players
        </h1>
      </div>

      {/* Selectors */}
      <div className="flex flex-col md:flex-row gap-3 mb-6">
        <PlayerSearchBox label="Search first player…" onSelect={(p) => setId('a', p.player_id)} />
        <span className="self-center font-display text-text-muted text-xs uppercase">vs</span>
        <PlayerSearchBox label="Search second player…" onSelect={(p) => setId('b', p.player_id)} />
      </div>

      {(!playerA || !playerB) && (
        <div className="rounded-xl border border-border bg-surface-850 p-10 text-center text-text-muted text-sm">
          Pick two players to compare their season stats and weekly fantasy production.
        </div>
      )}

      {playerA && playerB && (
        <div className="space-y-6">
          {/* Headers */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border border-border bg-surface-850 p-4" style={{ borderTopColor: colorA, borderTopWidth: 3 }}>
              <PlayerHeader player={playerA} color={colorA} onClear={() => setId('a', null)} />
            </div>
            <div className="rounded-xl border border-border bg-surface-850 p-4" style={{ borderTopColor: colorB, borderTopWidth: 3 }}>
              <PlayerHeader player={playerB} color={colorB} onClear={() => setId('b', null)} />
            </div>
          </div>

          {/* Season stats side by side */}
          <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
            <div className="px-5 py-3 border-b border-border bg-surface-800/50">
              <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
                Season Stats
              </h2>
            </div>
            {playerA.current_stats && playerB.current_stats ? (
              <table className="w-full text-sm">
                <tbody>
                  {rows.map((row) => {
                    const sA = playerA.current_stats!;
                    const sB = playerB.current_stats!;
                    const aWins = row.raw(sA) > row.raw(sB);
                    const bWins = row.raw(sB) > row.raw(sA);
                    return (
                      <tr key={row.label} className="border-b border-border/50 last:border-0">
                        <td className={`px-5 py-2.5 text-right tabular-nums w-1/3 ${aWins ? 'font-bold text-text-primary' : 'text-text-secondary'}`}>
                          {row.get(sA)}
                        </td>
                        <td className="px-2 py-2.5 text-center text-[10px] uppercase tracking-wider text-text-muted font-display w-1/3">
                          {row.label}
                        </td>
                        <td className={`px-5 py-2.5 text-left tabular-nums w-1/3 ${bWins ? 'font-bold text-text-primary' : 'text-text-secondary'}`}>
                          {row.get(sB)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <p className="p-5 text-xs text-text-muted">Season stats missing for one of the players.</p>
            )}
          </div>

          {/* Weekly PPR overlay */}
          <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
            <div className="px-5 py-3 border-b border-border bg-surface-800/50 flex items-center justify-between">
              <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
                Weekly Fantasy Points (PPR)
              </h2>
              <select
                value={season}
                onChange={(e) => setSeason(Number(e.target.value))}
                className="bg-surface-800 border border-border rounded px-2 py-1 text-xs text-text-secondary"
              >
                {SEASON_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="p-5">
              {loading && <Spinner text="Loading weekly stats…" />}
              {!loading && chartData.length === 0 && (
                <p className="text-xs text-text-muted">No weekly data for either player in {season}.</p>
              )}
              {!loading && chartData.length > 0 && (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="week" tick={{ fontSize: 11, fill: 'var(--color-text-muted)', fontFamily: 'Oswald, sans-serif' }} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--color-text-muted)', fontFamily: 'Oswald, sans-serif' }} />
                    <Tooltip contentStyle={tooltipStyle} labelFormatter={(l) => `Week ${l}`} />
                    <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'Oswald, sans-serif' }} />
                    <Line
                      type="monotone" dataKey="a" name={playerA.full_name}
                      stroke={colorA} strokeWidth={2} dot={{ r: 3, fill: colorA }} connectNulls
                    />
                    <Line
                      type="monotone" dataKey="b" name={playerB.full_name}
                      stroke={colorB} strokeWidth={2} strokeDasharray="6 3"
                      dot={{ r: 3, fill: colorB }} connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
