import { useState } from 'react';
import { api } from '../../api/client';
import type { ScheduleOutlook } from '../../api/types';
import { PosBadge } from './shared';
import RosterImportHelper from './RosterImportHelper';

interface Props {
  rosterIds: number[];
  onImported: (ids: number[]) => void;
}

const DIFFICULTY_CLASS: Record<string, string> = {
  hard: 'text-loss',
  medium: 'text-text-muted',
  easy: 'text-win',
};

/**
 * Draft-time planning: does my roster stack byes, and which of my players
 * face a brutal stretch in the fantasy playoffs (weeks 15-17)?
 */
export default function ScheduleTab({ rosterIds, onImported }: Props) {
  const [outlook, setOutlook] = useState<ScheduleOutlook | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (rosterIds.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.getScheduleOutlook(rosterIds);
      setOutlook(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to build schedule outlook');
    } finally {
      setLoading(false);
    }
  }

  if (rosterIds.length === 0) {
    return (
      <div className="space-y-6">
        <p className="text-sm text-text-muted">
          Import your roster to see bye-week collisions and each player's
          strength of schedule through the fantasy playoffs.
        </p>
        <RosterImportHelper onImported={onImported} />
      </div>
    );
  }

  const nameById = new Map(outlook?.players.map((p) => [p.player_id, p.full_name]) ?? []);
  const collisionWeeks = Object.entries(outlook?.bye_collisions ?? {});

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4">
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-2 rounded bg-accent text-surface-900 font-display text-sm font-semibold uppercase tracking-widest disabled:opacity-50"
        >
          {loading ? 'Working…' : 'Check schedule'}
        </button>
        <span className="text-xs text-text-muted">{rosterIds.length} players</span>
      </div>

      {error && <p className="text-sm text-loss">{error}</p>}

      {outlook && (
        <>
          {collisionWeeks.map(([week, ids]) => (
            <p key={week} className="text-sm text-loss border border-loss/40 rounded px-3 py-2">
              ⚠ {ids.length} players share bye week {week}:{' '}
              {ids.map((id) => nameById.get(id) ?? id).join(', ')}
            </p>
          ))}

          <div>
            <h3 className="font-display text-lg font-semibold text-text-primary">
              Playoff outlook (weeks 15–17)
            </h3>
            <table className="w-full mt-3 text-sm">
              <thead>
                <tr className="text-text-muted text-xs uppercase tracking-widest">
                  <th className="text-left py-2">Player</th>
                  <th className="text-center py-2">Bye</th>
                  <th className="text-center py-2">Wk15</th>
                  <th className="text-center py-2">Wk16</th>
                  <th className="text-center py-2">Wk17</th>
                  <th className="text-right py-2">SOS</th>
                </tr>
              </thead>
              <tbody>
                {outlook.players.map((p) => (
                  <tr key={p.player_id} className="border-t border-border">
                    <td className="py-2">
                      <span className="inline-flex items-center gap-2">
                        {p.full_name}
                        {p.position && <PosBadge pos={p.position} />}
                      </span>
                    </td>
                    <td className="py-2 text-center text-text-muted">
                      {p.bye_week != null ? `Bye ${p.bye_week}` : '—'}
                    </td>
                    {[15, 16, 17].map((w) => {
                      const wk = p.playoff_weeks.find((x) => x.week === w);
                      return (
                        <td key={w} className="py-2 text-center">
                          {wk ? (
                            <span className={DIFFICULTY_CLASS[wk.difficulty ?? ''] ?? ''}>
                              {wk.opponent_team_abbr ?? '—'}
                            </span>
                          ) : (
                            <span className="text-text-muted">—</span>
                          )}
                        </td>
                      );
                    })}
                    <td className="py-2 text-right tabular-nums">
                      {p.playoff_sos_score != null ? p.playoff_sos_score.toFixed(1) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
