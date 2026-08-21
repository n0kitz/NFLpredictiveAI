import { useState } from 'react';
import { api } from '../../api/client';
import type { LineupAdvice, StartSitRank } from '../../api/types';
import { ACTIVE_SEASON } from '../../config';
import { useLeagueSettings } from './leagueSettings';
import { PosBadge, Headshot } from './shared';
import RosterImportHelper from './RosterImportHelper';

interface Props {
  rosterIds: number[];
  onImported: (ids: number[]) => void;
}

/**
 * "Give me my team, tell me what to change."
 *
 * Unlike the Optimizer tab (which searches every player in the league, a DFS
 * question), everything here is constrained to the roster you own.
 */
export default function MyTeamTab({ rosterIds, onImported }: Props) {
  const [{ scoring, leagueSize }] = useLeagueSettings();
  const [week, setWeek] = useState(1);
  const [advice, setAdvice] = useState<LineupAdvice | null>(null);
  const [compare, setCompare] = useState<StartSitRank | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (rosterIds.length === 0) return;
    setLoading(true);
    setError(null);
    setCompare(null);
    try {
      const res = await api.getMyTeamLineup(
        rosterIds, week, ACTIVE_SEASON, undefined, scoring, leagueSize,
      );
      setAdvice(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to build lineup');
    } finally {
      setLoading(false);
    }
  }

  async function comparePosition(position: string) {
    if (!advice) return;
    const ids = [...advice.lineup, ...advice.bench]
      .filter((p) => p.position === position)
      .map((p) => p.player_id);
    if (ids.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.getStartSitRank(
        ids, week, ACTIVE_SEASON, 1, scoring, leagueSize,
      );
      setCompare(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to compare players');
    } finally {
      setLoading(false);
    }
  }

  if (rosterIds.length === 0) {
    return (
      <div className="space-y-6">
        <p className="text-sm text-text-muted">
          Import your roster to get a recommended lineup, suggested swaps and
          injury warnings for your own players.
        </p>
        <RosterImportHelper onImported={onImported} />
      </div>
    );
  }

  const positions = advice
    ? Array.from(
        new Set([...advice.lineup, ...advice.bench].map((p) => p.position ?? '')),
      ).filter((p) => ['QB', 'RB', 'WR', 'TE'].includes(p))
    : [];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-xs uppercase tracking-widest text-text-muted">
          Week
          <select
            aria-label="Week"
            value={week}
            onChange={(e) => setWeek(Number(e.target.value))}
            className="mt-1 block bg-surface-800 border border-border rounded px-3 py-2 text-sm text-text-primary"
          >
            {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
              <option key={w} value={w}>{w}</option>
            ))}
          </select>
        </label>
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-2 rounded bg-accent text-surface-900 font-display text-sm font-semibold uppercase tracking-widest disabled:opacity-50"
        >
          {loading ? 'Working…' : 'Recommend lineup'}
        </button>
        <span className="text-xs text-text-muted">
          {rosterIds.length} players · {scoring} · {leagueSize}-team
        </span>
      </div>

      {error && <p className="text-sm text-loss">{error}</p>}

      {advice && (
        <>
          {advice.warnings.map((w) => (
            <p key={w} className="text-sm text-loss border border-loss/40 rounded px-3 py-2">
              ⚠ {w}
            </p>
          ))}

          <div>
            <h3 className="font-display text-lg font-semibold text-text-primary">
              Recommended lineup — {advice.projected_points.toFixed(1)} pts
            </h3>
            <table className="w-full mt-3 text-sm">
              <thead>
                <tr className="text-text-muted text-xs uppercase tracking-widest">
                  <th className="text-left py-2">Slot</th>
                  <th className="text-left py-2">Player</th>
                  <th className="text-right py-2">Proj</th>
                </tr>
              </thead>
              <tbody>
                {advice.lineup.map((p) => (
                  <tr key={p.player_id} className="border-t border-border">
                    <td className="py-2 text-text-muted">{p.slot}</td>
                    <td className="py-2">
                      <span className="inline-flex items-center gap-2">
                        <Headshot url={null} name={p.full_name} />
                        {p.full_name}
                        {p.position && <PosBadge pos={p.position} />}
                      </span>
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {p.projected_points.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <h3 className="font-display text-lg font-semibold text-text-primary">
              Suggested changes
            </h3>
            {advice.swaps.length === 0 ? (
              <p className="text-sm text-win mt-2">
                Your lineup is already optimal — no changes needed.
              </p>
            ) : (
              <ul className="mt-2 space-y-2">
                {advice.swaps.map((s) => (
                  <li key={`${s.start_player_id}-${s.sit_player_id}`} className="text-sm">
                    <span className="text-win font-semibold">
                      Start {s.start_name}
                    </span>{' '}
                    over {s.sit_name}{' '}
                    <span className="text-text-muted">
                      (+{s.point_delta.toFixed(1)} pts)
                    </span>
                    <div className="text-xs text-text-muted">{s.reason}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h3 className="font-display text-lg font-semibold text-text-primary">
              Who should I start?
            </h3>
            <div className="flex flex-wrap gap-2 mt-2">
              {positions.map((pos) => (
                <button
                  key={pos}
                  onClick={() => comparePosition(pos)}
                  className="px-3 py-1.5 rounded border border-border text-xs uppercase tracking-widest text-text-secondary hover:text-accent"
                >
                  Compare {pos}s
                </button>
              ))}
            </div>
            {compare && (
              <ol className="mt-3 space-y-2">
                {compare.ranked.map((r) => (
                  <li key={r.player_id} className="text-sm">
                    <span className={r.verdict === 'start' ? 'text-win font-semibold' : 'text-text-muted'}>
                      {r.rank}. {r.full_name} — {r.projected_points.toFixed(1)} pts
                      {r.verdict === 'start' ? ' (start)' : ' (sit)'}
                    </span>
                    <div className="text-xs text-text-muted">{r.reasoning}</div>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div>
            <h3 className="font-display text-sm uppercase tracking-widest text-text-muted">
              Bench
            </h3>
            <ul className="mt-2 text-sm text-text-secondary">
              {advice.bench.map((p) => (
                <li key={p.player_id} className="py-1 border-t border-border">
                  {p.full_name} · {p.position} · {p.projected_points.toFixed(1)} pts
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
