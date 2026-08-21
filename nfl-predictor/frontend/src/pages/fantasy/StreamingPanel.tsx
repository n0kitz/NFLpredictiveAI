import { useState } from 'react';
import { api } from '../../api/client';
import type { StreamingCandidate } from '../../api/types';
import { gradeColor } from './helpers';

interface Props {
  week: number;
  excludeIds: number[];
}

const POSITIONS = ['DST', 'K', 'QB'] as const;
type StreamPosition = typeof POSITIONS[number];

/**
 * matchup_grade() scores a position vs. an opponent — every candidate here
 * is the one presumed starter per team, not a full depth chart, since
 * teammates at the same position share an identical grade.
 */
export default function StreamingPanel({ week, excludeIds }: Props) {
  const [position, setPosition] = useState<StreamPosition | null>(null);
  const [candidates, setCandidates] = useState<StreamingCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(pos: StreamPosition) {
    setPosition(pos);
    setLoading(true);
    setError(null);
    try {
      const res = await api.getStreamingCandidates(pos, week, undefined, excludeIds);
      setCandidates(res.candidates);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load streaming picks');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-border bg-surface-850 p-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h3 className="font-display text-sm font-semibold uppercase tracking-widest text-text-primary">
          Streaming picks — Week {week}
        </h3>
        <div className="flex gap-2">
          {POSITIONS.map((p) => (
            <button
              key={p}
              onClick={() => run(p)}
              className={`px-3 py-1.5 rounded border text-xs uppercase tracking-widest transition-colors ${
                position === p
                  ? 'border-accent text-accent'
                  : 'border-border text-text-muted hover:text-text-secondary'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-loss">{error}</p>}
      {loading && <p className="text-xs text-text-muted">Working…</p>}

      {position && !loading && !error && (
        candidates.length === 0 ? (
          <p className="text-xs text-text-muted">
            No available {position} candidates this week.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {candidates.map((c) => (
              <li key={c.player_id} className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 min-w-0">
                  <span
                    className="text-[9px] font-display font-bold uppercase px-1.5 py-0.5 rounded shrink-0"
                    style={{ color: gradeColor(c.grade), background: `${gradeColor(c.grade)}22` }}
                  >
                    {c.grade}
                  </span>
                  <span className="text-text-primary truncate">{c.full_name}</span>
                  <span className="text-text-muted text-xs shrink-0">
                    {c.team_abbr} vs {c.opponent_team_abbr}
                  </span>
                </span>
                <span className="text-xs text-text-muted tabular-nums shrink-0">
                  {c.score.toFixed(1)}
                </span>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  );
}
