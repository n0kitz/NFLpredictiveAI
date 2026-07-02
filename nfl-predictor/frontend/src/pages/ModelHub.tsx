import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart, Bar, ComposedChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, ReferenceLine, Legend,
} from 'recharts';
import { api } from '../api/client';
import type {
  AccuracyStats, AccuracyDetail, ModelInfo, DataCoverage,
  ValuePickHistoryResponse, NotableGameEntry,
} from '../api/types';
import Spinner from '../components/Spinner';
import { CURRENT_SEASON, recentSeasons } from '../config';

const ACCENT = 'var(--color-accent)';
const NEUTRAL = 'var(--color-text-secondary)';

const tooltipStyle = {
  backgroundColor: 'var(--color-surface-800)',
  border: '1px solid var(--color-border)',
  borderRadius: '6px',
  fontSize: '12px',
};
const axisStyle = { fontSize: 11, fill: 'var(--color-text-muted)', fontFamily: 'Oswald, sans-serif' };

const RANGE_OPTIONS = [2, 4, 6] as const;
const DETAIL_SEASONS = recentSeasons(6);

function seasonsParam(n: number): string {
  return Array.from({ length: n }, (_, i) => CURRENT_SEASON - n + 1 + i).join(',');
}

function Card({ title, subtitle, children }: {
  title: string; subtitle?: string; children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-850 p-5">
      <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
        {title}
      </h2>
      {subtitle && <p className="text-xs text-text-muted mt-1">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </div>
  );
}

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface-800 border border-border rounded-lg px-4 py-3">
      <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">{label}</div>
      <div className="font-display text-2xl font-bold text-text-primary">{value}</div>
      {sub && <div className="text-[11px] text-text-muted mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Calibration ────────────────────────────────────────────────────────────────

function bucketMidpoint(label: string): number {
  // '50-55%' → 52.5; '80%+' → 85
  const m = label.match(/^(\d+)-(\d+)/);
  if (m) return (Number(m[1]) + Number(m[2])) / 2;
  const single = label.match(/^(\d+)/);
  return single ? Number(single[1]) + 5 : 0;
}

function CalibrationChart({ calibration }: { calibration: AccuracyStats['calibration'] }) {
  const data = Object.entries(calibration)
    .map(([bucket, v]) => ({
      bucket,
      expected: bucketMidpoint(bucket),
      actual: v.total > 0 ? Math.round((v.correct / v.total) * 1000) / 10 : null,
      games: v.total,
    }))
    .sort((a, b) => a.expected - b.expected);

  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis dataKey="bucket" tick={axisStyle} />
        <YAxis domain={[0, 100]} tick={axisStyle} tickFormatter={(v) => `${v}%`} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value, name) =>
            value === null || value === undefined ? ['—', String(name)] : [`${value}%`, String(name)]}
          labelFormatter={(label) => {
            const row = data.find((d) => d.bucket === label);
            return `Predicted ${label} (${row?.games ?? 0} games)`;
          }}
        />
        <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'Oswald, sans-serif' }} />
        <Bar dataKey="actual" name="Actual win rate" fill={ACCENT} radius={[2, 2, 0, 0]} />
        <Line
          dataKey="expected" name="Perfectly calibrated" stroke={NEUTRAL}
          strokeWidth={2} strokeDasharray="6 4" dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── Notable games ──────────────────────────────────────────────────────────────

function NotableList({ games, tone }: { games: NotableGameEntry[]; tone: 'hit' | 'miss' }) {
  if (games.length === 0) {
    return <p className="text-xs text-text-muted">No games in this category.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {games.map((g) => (
        <li key={g.game_id}>
          <Link
            to={`/games/${g.game_id}`}
            className="flex items-center gap-2 text-xs rounded-md px-2 py-1.5 bg-surface-800 border border-border hover:border-accent/50 transition-colors"
          >
            <span
              className="font-display font-bold w-12 text-center"
              style={{ color: tone === 'hit' ? 'var(--color-win)' : 'var(--color-loss)' }}
            >
              {(g.winner_prob * 100).toFixed(0)}%
            </span>
            <span className="text-text-secondary">Wk {g.week}</span>
            <span className="text-text-primary font-medium">
              {g.away_team} @ {g.home_team}
            </span>
            <span className="ml-auto text-text-muted">
              picked {g.predicted_winner}{tone === 'miss' ? ` — ${g.actual_winner} won` : ''}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ModelHub() {
  const [range, setRange] = useState<number>(RANGE_OPTIONS[0]);
  const [acc, setAcc] = useState<AccuracyStats | null>(null);
  const [accLoading, setAccLoading] = useState(true);
  const [accError, setAccError] = useState<string | null>(null);

  const [detailSeason, setDetailSeason] = useState(DETAIL_SEASONS[0]);
  const [detail, setDetail] = useState<AccuracyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(true);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [picks, setPicks] = useState<ValuePickHistoryResponse | null>(null);
  const [coverage, setCoverage] = useState<DataCoverage | null>(null);

  useEffect(() => {
    let cancelled = false;
    setAccLoading(true);
    setAccError(null);
    api.getAccuracy(seasonsParam(range))
      .then((d) => { if (!cancelled) setAcc(d); })
      .catch((e) => { if (!cancelled) setAccError(e.message); })
      .finally(() => { if (!cancelled) setAccLoading(false); });
    return () => { cancelled = true; };
  }, [range]);

  useEffect(() => {
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    api.getAccuracyDetail(detailSeason)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((e) => { if (!cancelled) setDetailError(e.message); })
      .finally(() => { if (!cancelled) setDetailLoading(false); });
    return () => { cancelled = true; };
  }, [detailSeason]);

  useEffect(() => {
    let cancelled = false;
    api.getModelInfo().then((d) => { if (!cancelled) setInfo(d); }).catch(() => {});
    api.getValuePicksHistory().then((d) => { if (!cancelled) setPicks(d); }).catch(() => {});
    api.getDataCoverage().then((d) => { if (!cancelled) setCoverage(d); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const seasonBars = acc
    ? Object.entries(acc.season_accuracy)
        .map(([season, v]) => ({
          season,
          accuracy: Math.round(v.accuracy * 1000) / 10,
          record: `${v.correct}-${v.total - v.correct}`,
        }))
        .sort((a, b) => Number(a.season) - Number(b.season))
    : [];

  const weeklyBars = detail
    ? detail.weekly.map((w) => ({
        week: w.week,
        accuracy: Math.round(w.accuracy * 1000) / 10,
        record: `${w.correct}-${w.total - w.correct}`,
      }))
    : [];

  const maxImportance = info?.feature_importance[0]?.importance ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between animate-fade-up">
        <div>
          <div className="font-display text-[11px] font-bold tracking-[0.2em] uppercase text-accent">
            Transparency
          </div>
          <h1 className="font-display text-2xl font-bold text-text-primary uppercase tracking-tight">
            Model Hub
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">Backtest range</span>
          {RANGE_OPTIONS.map((n) => (
            <button
              key={n}
              onClick={() => setRange(n)}
              className={`px-2.5 py-1 rounded text-xs font-display font-semibold transition-colors ${
                range === n
                  ? 'bg-accent/20 text-accent'
                  : 'bg-surface-800 text-text-muted hover:text-text-secondary'
              }`}
            >
              {n} seasons
            </button>
          ))}
        </div>
      </div>

      {accError && <p className="text-red-400 text-sm">{accError}</p>}
      {accLoading && <Spinner text="Replaying seasons (first load can take ~30s)..." />}

      {acc && !accLoading && (
        <>
          {/* Headline tiles */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatTile
              label="Backtest accuracy"
              value={`${(acc.accuracy * 100).toFixed(1)}%`}
              sub={`${acc.correct_predictions}/${acc.total_games} games, ${acc.seasons.join(', ')}`}
            />
            <StatTile
              label="High-confidence games"
              value={acc.by_confidence.high?.total
                ? `${(acc.by_confidence.high.accuracy * 100).toFixed(1)}%`
                : '—'}
              sub={acc.by_confidence.high?.total ? `${acc.by_confidence.high.total} games` : 'none'}
            />
            <StatTile
              label="Active model"
              value={info ? info.active_model.replace('_', ' ') : '…'}
              sub={info?.feature_count ? `${info.feature_count} features (ML)` : undefined}
            />
            <StatTile
              label="Every pick is leak-free"
              value="Cutoff-aware"
              sub="Each game predicted with pre-game data only"
            />
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <Card
              title="Calibration"
              subtitle="When the model says 70%, does it win 70% of the time? Bars near the dashed line = honest probabilities."
            >
              <CalibrationChart calibration={acc.calibration} />
            </Card>

            <Card title="Accuracy by season" subtitle="Regular-season backtest, one bar per season.">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={seasonBars}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="season" tick={axisStyle} />
                  <YAxis domain={[0, 100]} tick={axisStyle} tickFormatter={(v) => `${v}%`} />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(v, _n, entry) =>
                      [`${v}% (${(entry?.payload as { record?: string })?.record ?? ''})`, 'Accuracy']}
                  />
                  <ReferenceLine y={50} stroke={NEUTRAL} strokeDasharray="6 4" />
                  <Bar dataKey="accuracy" name="Accuracy" fill={ACCENT} radius={[2, 2, 0, 0]} maxBarSize={64} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[10px] text-text-muted mt-1">Dashed line = 50% coin flip.</p>
            </Card>
          </div>

          {/* Confidence tiers */}
          <Card title="Accuracy by confidence" subtitle="The model should be more accurate when it claims to be more confident.">
            <div className="space-y-2">
              {(['high', 'medium', 'low'] as const).map((tier) => {
                const t = acc.by_confidence[tier];
                if (!t) return null;
                const pct = t.total > 0 ? t.accuracy * 100 : 0;
                return (
                  <div key={tier} className="flex items-center gap-3 text-xs">
                    <span className="w-16 uppercase font-display font-semibold text-text-secondary">{tier}</span>
                    <div className="flex-1 h-3 bg-surface-800 rounded overflow-hidden">
                      <div
                        className="h-full rounded-r"
                        style={{ width: `${pct}%`, backgroundColor: ACCENT }}
                      />
                    </div>
                    <span className="w-36 text-right text-text-primary font-medium whitespace-nowrap">
                      {t.total > 0 ? `${pct.toFixed(1)}% · ${t.total} games` : 'no games'}
                    </span>
                  </div>
                );
              })}
            </div>
          </Card>
        </>
      )}

      {/* Season detail */}
      <Card title="Season replay" subtitle="Week-by-week record plus the calls that defined the season.">
        <div className="flex items-center gap-2 mb-4">
          <label className="text-xs text-text-muted">Season</label>
          <select
            value={detailSeason}
            onChange={(e) => setDetailSeason(Number(e.target.value))}
            className="bg-surface-800 border border-border rounded px-2 py-1 text-sm text-text-primary"
          >
            {DETAIL_SEASONS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          {detail && !detailLoading && detail.total_games > 0 && (
            <span className="text-xs text-text-muted">
              {detail.correct_predictions}-{detail.total_games - detail.correct_predictions} ·{' '}
              {(detail.accuracy * 100).toFixed(1)}%
            </span>
          )}
        </div>

        {detailError && <p className="text-red-400 text-sm">{detailError}</p>}
        {detailLoading && <Spinner text="Replaying season..." />}
        {detail && !detailLoading && detail.total_games === 0 && (
          <p className="text-xs text-text-muted">No completed games for {detailSeason}.</p>
        )}
        {detail && !detailLoading && detail.total_games > 0 && (
          <div className="space-y-5">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={weeklyBars}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="week" tick={axisStyle} />
                <YAxis domain={[0, 100]} tick={axisStyle} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(v, _n, entry) =>
                    [`${v}% (${(entry?.payload as { record?: string })?.record ?? ''})`, 'Accuracy']}
                  labelFormatter={(l) => `Week ${l}`}
                />
                <ReferenceLine y={50} stroke={NEUTRAL} strokeDasharray="6 4" />
                <Bar dataKey="accuracy" name="Accuracy" fill={ACCENT} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="grid md:grid-cols-2 gap-5">
              <div>
                <h3 className="text-[10px] uppercase tracking-wider font-display font-semibold mb-2"
                  style={{ color: 'var(--color-win)' }}>
                  Confident calls that hit
                </h3>
                <NotableList games={detail.best_calls} tone="hit" />
              </div>
              <div>
                <h3 className="text-[10px] uppercase tracking-wider font-display font-semibold mb-2"
                  style={{ color: 'var(--color-loss)' }}>
                  Confident calls that missed
                </h3>
                <NotableList games={detail.biggest_misses} tone="miss" />
              </div>
            </div>
          </div>
        )}
      </Card>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Value picks track record */}
        <Card
          title="Edge picks track record"
          subtitle="Games where the model disagreed with Vegas by ≥4 points of win probability."
        >
          {!picks || picks.total === 0 ? (
            <p className="text-xs text-text-muted">
              No edge picks recorded yet — they're logged automatically when Vegas odds are
              available for upcoming games.
            </p>
          ) : (
            <div className="space-y-3">
              <div className="flex gap-3">
                <StatTile
                  label="Hit rate"
                  value={picks.hit_rate !== null ? `${(picks.hit_rate * 100).toFixed(0)}%` : '—'}
                  sub={`${picks.correct}/${picks.resolved} resolved`}
                />
                <StatTile label="Picks logged" value={String(picks.total)} />
              </div>
              <ul className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                {picks.picks.slice(0, 15).map((p) => (
                  <li key={p.id} className="flex items-center gap-2 text-xs bg-surface-800 border border-border rounded-md px-2 py-1.5">
                    <span className="text-text-primary font-medium">{p.away_abbr} @ {p.home_abbr}</span>
                    <span className="text-text-muted">
                      edge {(Math.abs(p.edge) * 100).toFixed(1)}pp {p.edge_side}
                    </span>
                    <span
                      className="ml-auto font-display font-bold"
                      style={{
                        color: p.correct === null
                          ? 'var(--color-text-muted)'
                          : p.correct ? 'var(--color-win)' : 'var(--color-loss)',
                      }}
                    >
                      {p.correct === null ? 'PENDING' : p.correct ? 'HIT' : 'MISS'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        {/* Feature importance */}
        <Card
          title="What the ML model looks at"
          subtitle="Global feature importance of the gradient-boosting model (top 12 of 34 features)."
        >
          {!info || info.feature_importance.length === 0 ? (
            <p className="text-xs text-text-muted">
              Feature importance is available when the ML model is loaded.
            </p>
          ) : (
            <div className="space-y-1.5">
              {info.feature_importance.map((f) => (
                <div key={f.feature} className="flex items-center gap-3 text-xs">
                  <span className="w-44 truncate text-text-secondary" title={f.label}>{f.label}</span>
                  <div className="flex-1 h-2.5 bg-surface-800 rounded overflow-hidden">
                    <div
                      className="h-full rounded-r"
                      style={{
                        width: `${maxImportance > 0 ? (f.importance / maxImportance) * 100 : 0}%`,
                        backgroundColor: ACCENT,
                      }}
                    />
                  </div>
                  <span className="w-12 text-right text-text-muted">
                    {(f.importance * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Data coverage */}
      <Card title="Data coverage" subtitle="What's in the database — and what each table powers.">
        {!coverage ? (
          <Spinner />
        ) : (
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-surface-800">
                  <th className="text-left px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold">Table</th>
                  <th className="text-right px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold">Rows</th>
                  <th className="text-center px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold">Seasons</th>
                  <th className="text-left px-3 py-2 text-[10px] uppercase tracking-wider text-text-muted font-semibold hidden md:table-cell">Powers</th>
                </tr>
              </thead>
              <tbody>
                {coverage.tables.map((t) => (
                  <tr key={t.table} className="border-b border-border/50">
                    <td className="px-3 py-2 font-mono text-text-primary">{t.table}</td>
                    <td className="px-3 py-2 text-right text-text-secondary">
                      {t.rows > 0 ? t.rows.toLocaleString() : (
                        <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-surface-700 text-text-muted">
                          empty
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-center text-text-secondary">
                      {t.season_min !== null
                        ? t.season_min === t.season_max ? t.season_min : `${t.season_min}–${t.season_max}`
                        : '—'}
                    </td>
                    <td className="px-3 py-2 text-text-muted hidden md:table-cell">{t.powers}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
