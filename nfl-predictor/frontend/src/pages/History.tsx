import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { PredictionHistory } from '../api/types';
import Spinner from '../components/Spinner';
import { getTeamColors } from '../theme/teamColors';

export default function History() {
  const [data, setData] = useState<PredictionHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const limit = 30;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getPredictionHistory(limit, page * limit)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page]);

  return (
    <div>
      {/* Header */}
      <div className="mb-8 animate-fade-up">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-px w-6 bg-accent" />
          <span className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold">
            Track Record
          </span>
        </div>
        <h1 className="font-display text-3xl font-bold text-text-primary uppercase tracking-tight">
          Prediction History
        </h1>
      </div>

      {/* Accuracy cards */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8 animate-fade-up stagger-1">
          <StatCard label="Total Predictions" value={String(data.total)} />
          <StatCard label="Resolved" value={String(data.resolved)} />
          <StatCard label="Correct" value={String(data.correct)} color="var(--color-win)" />
          <StatCard
            label="Accuracy"
            value={data.accuracy !== null ? `${(data.accuracy * 100).toFixed(1)}%` : 'N/A'}
            color={data.accuracy !== null && data.accuracy >= 0.5 ? 'var(--color-win)' : undefined}
          />
        </div>
      )}

      {loading && <Spinner text="Loading history..." />}

      {/* Table */}
      {data && data.predictions.length > 0 && (
        <div className="rounded-lg border border-border bg-surface-850 overflow-hidden animate-fade-up stagger-2">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] text-text-muted uppercase tracking-wider font-display border-b border-border bg-surface-800/50">
                  <th className="text-left px-4 py-3">Date</th>
                  <th className="text-left px-4 py-3">Matchup</th>
                  <th className="text-center px-4 py-3">Prediction</th>
                  <th className="text-center px-4 py-3">Prob</th>
                  <th className="text-center px-4 py-3">Conf</th>
                  <th className="text-center px-4 py-3">Result</th>
                </tr>
              </thead>
              <tbody>
                {data.predictions.map((p) => {
                  const pwColor = getTeamColors(p.predicted_winner_abbr).primary;
                  return (
                    <tr key={p.id} className="border-b border-border hover:bg-surface-700/30 transition-colors">
                      <td className="px-4 py-2.5 text-text-muted text-xs tabular-nums whitespace-nowrap">
                        {p.predicted_at.slice(0, 16)}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="text-text-secondary">
                          <Link to={`/teams/${p.away_abbr}`} className="hover:text-accent transition-colors">{p.away_abbr}</Link>
                          {' @ '}
                          <Link to={`/teams/${p.home_abbr}`} className="hover:text-accent transition-colors">{p.home_abbr}</Link>
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className="font-display font-bold" style={{ color: pwColor }}>
                          {p.predicted_winner_abbr}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center tabular-nums text-text-primary">
                        {(Math.max(p.home_prob, p.away_prob) * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className={`text-[10px] font-display uppercase tracking-wider font-medium ${
                          p.confidence === 'high' ? 'text-win' : p.confidence === 'medium' ? 'text-tie' : 'text-text-muted'
                        }`}>
                          {p.confidence}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {p.correct === null ? (
                          <span className="text-text-muted text-xs">Pending</span>
                        ) : p.correct ? (
                          <span className="text-win font-display font-bold text-xs">CORRECT</span>
                        ) : (
                          <span className="text-loss font-display font-bold text-xs">WRONG</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="text-xs font-display uppercase tracking-wider text-accent disabled:text-text-muted disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-xs text-text-muted">
              Page {page + 1}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={data.predictions.length < limit}
              className="text-xs font-display uppercase tracking-wider text-accent disabled:text-text-muted disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {data && data.predictions.length === 0 && !loading && (
        <div className="text-center py-16">
          <p className="text-text-muted text-sm">No predictions yet. Go to the <Link to="/predict" className="text-accent hover:text-accent-hover">Predict</Link> page to make your first one!</p>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-lg bg-surface-850 border border-border p-4">
      <p className="font-display text-[10px] uppercase tracking-[0.2em] text-text-muted font-semibold mb-1">
        {label}
      </p>
      <p className="font-display text-2xl font-bold tabular-nums" style={color ? { color } : undefined}>
        {value}
      </p>
    </div>
  );
}
