import { useState } from 'react';
import { api } from '../../api/client';
import type { FaabCandidate } from '../../api/types';
import { useLeagueSettings } from './leagueSettings';

interface Props {
  week: number;
  rosterIds: number[];
}

const TIER_CLASS: Record<FaabCandidate['tier'], string> = {
  'must-add': 'text-win bg-win/15',
  priority: 'text-win bg-win/10',
  solid: 'text-yellow-400 bg-yellow-500/15',
  speculative: 'text-text-muted bg-surface-700',
};

/**
 * Ranks waiver targets against the weakest player YOU already roster at
 * that position — not raw VBD, which only says how good a player is
 * relative to the league.
 */
export default function FaabPanel({ week, rosterIds }: Props) {
  const [{ scoring, leagueSize }] = useLeagueSettings();
  const [budget, setBudget] = useState(100);
  const [candidates, setCandidates] = useState<FaabCandidate[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getFaabRecommendations(
        rosterIds, week, undefined, 'all', scoring, leagueSize, budget,
      );
      setCandidates(res.candidates);
      setLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load FAAB recommendations');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-border bg-surface-850 p-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h3 className="font-display text-sm font-semibold uppercase tracking-widest text-text-primary">
          FAAB targets — Week {week}
        </h3>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-text-muted">
            Budget
            <input
              aria-label="Budget remaining"
              type="number"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="w-16 bg-surface-800 border border-border rounded px-2 py-1 text-xs text-text-primary"
            />
          </label>
          <button
            onClick={run}
            disabled={loading}
            className="px-3 py-1.5 rounded bg-accent text-surface-900 font-display text-xs font-semibold uppercase tracking-widest disabled:opacity-50"
          >
            {loading ? 'Working…' : 'Find FAAB targets'}
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-loss">{error}</p>}

      {loaded && !loading && !error && (
        candidates.length === 0 ? (
          <p className="text-xs text-text-muted">
            No waiver target beats your roster's replacement level this week.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {candidates.map((c) => (
              <li key={c.player_id} className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 min-w-0">
                  <span className={`text-[9px] font-display font-bold uppercase px-1.5 py-0.5 rounded shrink-0 ${TIER_CLASS[c.tier]}`}>
                    {c.tier}
                  </span>
                  <span className="text-text-primary truncate">{c.full_name}</span>
                  <span className="text-text-muted text-xs shrink-0">
                    {c.position} · {c.team_abbr}
                  </span>
                  <span className="text-win text-xs tabular-nums shrink-0">
                    +{c.delta.toFixed(1)}
                  </span>
                </span>
                <span className="text-xs text-text-muted tabular-nums shrink-0">
                  {c.suggested_bid_pct}% (${c.suggested_bid_amount})
                </span>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  );
}
