import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { PlayerWeeklyStatsResponse, PlayerWeekCell } from '../api/types';
import { LAST_COMPLETED_SEASON, recentSeasons } from '../config';
import Spinner from './Spinner';

interface Props {
  playerId: number;
  position: string | null;
  defaultSeason?: number;
}

// Weekly stats only exist for completed seasons; drop the in-progress current
// season so the default lands on a year that actually has game data.
const SEASON_OPTIONS = recentSeasons(8).filter((s) => s <= LAST_COMPLETED_SEASON);

/** A week counts as "played" when it has a result or any meaningful stat line. */
function played(c: PlayerWeekCell): boolean {
  return (
    c.result != null ||
    c.snap_pct > 0 ||
    c.fantasy_points_ppr !== 0 ||
    c.targets > 0 ||
    c.rush_attempts > 0 ||
    c.pass_attempts > 0
  );
}

function resultColor(result: string | null): string {
  if (result === 'W') return 'var(--color-win)';
  if (result === 'L') return 'var(--color-loss)';
  if (result === 'T') return 'var(--color-tie)';
  return 'var(--color-text-muted)';
}

function Th({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-2 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold ${className}`}>
      {children}
    </th>
  );
}

function Td({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-2 py-2 tabular-nums ${className}`}>{children}</td>;
}

export default function PlayerGameLog({ playerId, position, defaultSeason }: Props) {
  const [season, setSeason] = useState(defaultSeason ?? LAST_COMPLETED_SEASON);
  const [data, setData] = useState<PlayerWeeklyStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getPlayerWeeklyStats(playerId, season)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e?.message ?? 'Failed to load game log'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [playerId, season]);

  const pos = (position ?? '').toUpperCase();
  const isQB = pos === 'QB';
  const isRB = pos === 'RB' || pos === 'FB';
  const isRec = pos === 'WR' || pos === 'TE';

  const games = (data?.weeks ?? []).filter((c) => !c.is_bye && played(c));

  return (
    <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
      <div className="px-5 py-3 border-b border-border bg-surface-800/50 flex items-center justify-between">
        <h3 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-text-muted">Game Log</h3>
        <select
          value={season}
          onChange={(e) => setSeason(Number(e.target.value))}
          className="bg-surface-800 border border-border rounded px-2 py-1 text-xs text-text-secondary focus:outline-none focus:border-accent"
        >
          {SEASON_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {loading && <div className="p-5"><Spinner text="Loading game log…" /></div>}
      {error && !loading && <div className="p-5 text-text-muted text-xs">{error}</div>}
      {!loading && !error && games.length === 0 && (
        <div className="p-8 text-center text-text-muted text-xs">No game data for {season}.</div>
      )}

      {!loading && !error && games.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <Th className="text-left">Wk</Th>
                <Th className="text-left">Opp</Th>
                <Th className="text-left">Result</Th>
                {isQB && <><Th>C/A</Th><Th>Pass</Th><Th>TD</Th><Th>INT</Th><Th>Rush</Th></>}
                {isRB && <><Th>Car</Th><Th>Rush</Th><Th>TD</Th><Th>Rec</Th><Th>Rec Yd</Th></>}
                {isRec && <><Th>Tgt</Th><Th>Rec</Th><Th>Yds</Th><Th>TD</Th></>}
                {!isQB && !isRB && !isRec && <><Th>Pass</Th><Th>Rush</Th><Th>Rec</Th></>}
                <Th>Snap%</Th>
                <Th>PPR</Th>
              </tr>
            </thead>
            <tbody>
              {games.map((c, idx) => (
                <tr key={c.week} className={`border-b border-border/50 ${idx % 2 ? 'bg-surface-850' : 'bg-surface-900'}`}>
                  <Td className="text-left text-text-secondary">{c.week}</Td>
                  <Td className="text-left">
                    {c.opponent_abbr ? (
                      <Link to={`/teams/${c.opponent_abbr}`} className="text-text-secondary hover:text-accent transition-colors">
                        <span className="text-text-muted">{c.is_home ? 'vs' : '@'}</span> {c.opponent_abbr}
                      </Link>
                    ) : '—'}
                  </Td>
                  <Td className="text-left">
                    {c.result ? (
                      <span style={{ color: resultColor(c.result) }} className="font-semibold">
                        {c.result} {c.team_score}–{c.opp_score}
                      </span>
                    ) : <span className="text-text-muted">—</span>}
                  </Td>
                  {isQB && (
                    <>
                      <Td className="text-center text-text-secondary">{c.pass_completions}/{c.pass_attempts}</Td>
                      <Td className="text-center text-text-primary">{c.pass_yards}</Td>
                      <Td className="text-center text-text-secondary">{c.pass_tds}</Td>
                      <Td className="text-center text-text-secondary">{c.interceptions}</Td>
                      <Td className="text-center text-text-secondary">{c.rush_yards}</Td>
                    </>
                  )}
                  {isRB && (
                    <>
                      <Td className="text-center text-text-secondary">{c.rush_attempts}</Td>
                      <Td className="text-center text-text-primary">{c.rush_yards}</Td>
                      <Td className="text-center text-text-secondary">{c.rush_tds}</Td>
                      <Td className="text-center text-text-secondary">{c.receptions}</Td>
                      <Td className="text-center text-text-secondary">{c.rec_yards}</Td>
                    </>
                  )}
                  {isRec && (
                    <>
                      <Td className="text-center text-text-secondary">{c.targets}</Td>
                      <Td className="text-center text-text-secondary">{c.receptions}</Td>
                      <Td className="text-center text-text-primary">{c.rec_yards}</Td>
                      <Td className="text-center text-text-secondary">{c.rec_tds}</Td>
                    </>
                  )}
                  {!isQB && !isRB && !isRec && (
                    <>
                      <Td className="text-center text-text-secondary">{c.pass_yards}</Td>
                      <Td className="text-center text-text-secondary">{c.rush_yards}</Td>
                      <Td className="text-center text-text-secondary">{c.rec_yards}</Td>
                    </>
                  )}
                  <Td className="text-center text-text-muted">{c.snap_pct > 0 ? `${Math.round(c.snap_pct * 100)}%` : '—'}</Td>
                  <Td className="text-center text-accent font-semibold">{c.fantasy_points_ppr.toFixed(1)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
