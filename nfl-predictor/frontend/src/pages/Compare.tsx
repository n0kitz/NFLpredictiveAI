import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, Legend, ResponsiveContainer,
} from 'recharts';
import { useTeams, useTeamProfile, useTeamMetrics, useH2H } from '../hooks/useApi';
import TeamSelector from '../components/TeamSelector';
import Spinner from '../components/Spinner';
import DataBadge from '../components/DataBadge';
import H2HTimeline from '../components/H2HTimeline';
import TeamLogo from '../components/TeamLogo';
import { getTeamColors } from '../theme/teamColors';
import { api } from '../api/client';
import type { Prediction, TeamMetrics, UpcomingGame, SimulationResult } from '../api/types';

export default function Compare() {
  const { team1: paramT1, team2: paramT2 } = useParams<{ team1?: string; team2?: string }>();
  const navigate = useNavigate();
  const { data: teamList } = useTeams();

  const [t1, setT1] = useState(paramT1 ?? '');
  const [t2, setT2] = useState(paramT2 ?? '');

  useEffect(() => { if (paramT1) setT1(paramT1); }, [paramT1]);
  useEffect(() => { if (paramT2) setT2(paramT2); }, [paramT2]);

  useEffect(() => {
    if (t1 && t2) navigate(`/compare/${t1}/${t2}`, { replace: true });
  }, [t1, t2, navigate]);

  const bothSelected = !!(t1 && t2 && t1 !== t2);

  return (
    <div>
      <div className="mb-8 animate-fade-up">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-px w-6 bg-accent" />
          <span className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold">Side by Side</span>
        </div>
        <h1 className="font-display text-3xl font-bold text-text-primary uppercase tracking-tight">Compare</h1>
      </div>

      <div className="rounded-lg border border-border bg-surface-850 p-6 mb-8 animate-fade-up stagger-1">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-5 items-end">
          <TeamSelector teams={teamList?.teams ?? []} value={t1} onChange={setT1} label="Team 1" excludeAbbr={t2} />
          <div className="font-display text-text-muted text-xl font-bold self-center pt-5 hidden md:block">vs</div>
          <TeamSelector teams={teamList?.teams ?? []} value={t2} onChange={setT2} label="Team 2" excludeAbbr={t1} />
        </div>
      </div>

      {bothSelected && <CompareBody t1={t1} t2={t2} />}
    </div>
  );
}

// ── Quick Predict ─────────────────────────────────────────────────────────────

function QuickPredict({ t1, t2, c1, c2 }: { t1: string; t2: string; c1: string; c2: string }) {
  const [result, setResult] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const predict = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.predict(t1, t2);
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Prediction failed');
    } finally {
      setLoading(false);
    }
  }, [t1, t2]);

  return (
    <div className="rounded-lg border border-border bg-surface-850 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
          Predict This Matchup
        </h3>
        <DataBadge source="calculated" />
      </div>

      {error && <p className="text-red-400 text-sm mb-3">{error}</p>}
      {!result ? (
        <button
          onClick={predict}
          disabled={loading}
          className="w-full py-2.5 rounded-lg bg-accent text-surface-900 font-display font-bold text-sm uppercase tracking-widest hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {loading ? 'Predicting…' : `${t1} vs ${t2}`}
        </button>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="font-display text-sm font-bold" style={{ color: c1 }}>{t1}</span>
            <div className="flex-1 h-3 rounded-full overflow-hidden flex">
              <div className="h-full transition-all duration-700" style={{ width: `${(result.home_win_probability * 100).toFixed(0)}%`, backgroundColor: c1 }} />
              <div className="h-full transition-all duration-700" style={{ width: `${(result.away_win_probability * 100).toFixed(0)}%`, backgroundColor: c2 }} />
            </div>
            <span className="font-display text-sm font-bold" style={{ color: c2 }}>{t2}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span style={{ color: c1 }}>{(result.home_win_probability * 100).toFixed(1)}%</span>
            <span className="text-text-muted font-semibold">
              Winner: <span style={{ color: result.predicted_winner === t1 ? c1 : c2 }}>{result.predicted_winner}</span>
              {' '}({(result.predicted_winner_probability * 100).toFixed(1)}%)
            </span>
            <span style={{ color: c2 }}>{(result.away_win_probability * 100).toFixed(1)}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-display font-semibold uppercase px-2 py-0.5 rounded-full ${
              result.confidence === 'high' ? 'bg-win/10 text-win' :
              result.confidence === 'low'  ? 'bg-loss/10 text-loss' : 'bg-accent/10 text-accent'
            }`}>
              {result.confidence} confidence
            </span>
            <button onClick={() => setResult(null)} className="text-[10px] text-text-muted hover:text-text-secondary ml-auto">Reset</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Radar Chart ───────────────────────────────────────────────────────────────

function normalize(val: number, min: number, max: number) {
  return Math.round(Math.max(0, Math.min(100, ((val - min) / (max - min)) * 100)));
}

function TeamRadar({ m1, m2, t1, t2, c1, c2 }: {
  m1: TeamMetrics; m2: TeamMetrics; t1: string; t2: string; c1: string; c2: string;
}) {
  const dims = [
    {
      label: 'Offense',
      v1: normalize(m1.avg_points_scored, 14, 32),
      v2: normalize(m2.avg_points_scored, 14, 32),
    },
    {
      label: 'Defense',
      v1: normalize(32 - m1.avg_points_allowed, 0, 18),
      v2: normalize(32 - m2.avg_points_allowed, 0, 18),
    },
    {
      label: 'Home Form',
      v1: normalize(m1.home_win_pct, 0, 1) * 100 / 100,
      v2: normalize(m2.home_win_pct, 0, 1) * 100 / 100,
    },
    {
      label: 'Away Form',
      v1: normalize(m1.away_win_pct, 0, 1) * 100 / 100,
      v2: normalize(m2.away_win_pct, 0, 1) * 100 / 100,
    },
    {
      label: 'Rec. Form',
      v1: normalize(m1.recent_win_pct, 0, 1) * 100 / 100,
      v2: normalize(m2.recent_win_pct, 0, 1) * 100 / 100,
    },
    {
      label: 'Strength',
      v1: normalize(m1.offensive_strength + m1.defensive_strength, 0, 2),
      v2: normalize(m2.offensive_strength + m2.defensive_strength, 0, 2),
    },
  ];

  const radarData = dims.map((d) => ({
    dim: d.label,
    [t1]: d.v1,
    [t2]: d.v2,
  }));

  return (
    <div className="rounded-lg border border-border bg-surface-850 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
          Team Radar
        </h3>
        <DataBadge source="calculated" />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
          <PolarGrid stroke="var(--color-border)" />
          <PolarAngleAxis dataKey="dim" tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }} />
          <Radar name={t1} dataKey={t1} stroke={c1} fill={c1} fillOpacity={0.25} strokeWidth={2} />
          <Radar name={t2} dataKey={t2} stroke={c2} fill={c2} fillOpacity={0.25} strokeWidth={2} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Schedule Difficulty ───────────────────────────────────────────────────────

function diffBadge(d: 'easy' | 'medium' | 'hard') {
  const s = {
    easy:   'bg-win/15 text-win',
    medium: 'bg-yellow-500/15 text-yellow-400',
    hard:   'bg-loss/15 text-loss',
  }[d];
  return <span className={`text-[9px] font-display font-bold uppercase px-1.5 py-0.5 rounded ${s}`}>{d}</span>;
}

function ScheduleColumn({ abbr, color, season }: { abbr: string; color: string; season?: number }) {
  const [games, setGames] = useState<UpcomingGame[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getTeamUpcoming(abbr, season ?? 2025, 4)
      .then((r) => setGames(r.games))
      .catch(() => setGames([]))
      .finally(() => setLoading(false));
  }, [abbr, season]);

  return (
    <div className="flex-1">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-7 h-7 rounded-sm flex items-center justify-center text-[10px] font-display font-bold text-white" style={{ backgroundColor: color }}>
          {abbr}
        </span>
        <span className="text-xs font-display font-semibold text-text-primary uppercase">{abbr} — Next 4</span>
      </div>
      {loading ? (
        <p className="text-xs text-text-muted py-2">Loading…</p>
      ) : games.length === 0 ? (
        <p className="text-xs text-text-muted py-2">No upcoming games found.</p>
      ) : (
        <div className="space-y-2">
          {games.map((g) => (
            <div key={g.game_id} className="flex items-center gap-2 p-2 rounded-lg border border-border bg-surface-800/40">
              <span className="text-[9px] text-text-muted w-10 shrink-0">Wk {g.week}</span>
              <span className="text-xs font-semibold text-text-primary">{g.is_home ? 'vs' : '@'} {g.opp_abbr}</span>
              <span className="text-[10px] text-text-muted">{g.opp_record}</span>
              <span className="ml-auto">{diffBadge(g.difficulty)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Monte Carlo Simulator ─────────────────────────────────────────────────────

const SIM_OPTIONS = [500, 1000, 2500, 5000] as const;

function MonteCarloPanel({ t1, t2, c1, c2 }: { t1: string; t2: string; c1: string; c2: string }) {
  const [n, setN] = useState<number>(1000);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // t1 is "home" in the URL param sense (left team), t2 is "away"
      const res = await api.simulateGame(t1, t2, n);
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      setLoading(false);
    }
  }, [t1, t2, n]);

  // reset when teams change
  useEffect(() => { setResult(null); setError(null); }, [t1, t2]);

  const homePct = result ? result.home_win_pct * 100 : 50;
  const awayPct = result ? result.away_win_pct * 100 : 50;

  return (
    <div className="rounded-lg border border-border bg-surface-850 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
          Monte Carlo Simulator
        </h3>
        <DataBadge source="calculated" />
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-center gap-1 bg-surface-700 rounded-sm p-0.5">
          {SIM_OPTIONS.map((opt) => (
            <button
              key={opt}
              onClick={() => setN(opt)}
              className={`px-2.5 py-1 rounded-sm text-[11px] font-display font-semibold transition-colors ${
                n === opt ? 'bg-accent text-surface-900' : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {opt.toLocaleString()}
            </button>
          ))}
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="flex-1 py-1.5 rounded-sm bg-accent text-surface-900 font-display font-bold text-[11px] uppercase tracking-widest hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {loading ? 'Simulating…' : `Simulate ${n.toLocaleString()} Games`}
        </button>
        {result && (
          <button onClick={() => setResult(null)} className="text-[10px] text-text-muted hover:text-text-secondary shrink-0">Reset</button>
        )}
      </div>

      {error && <p className="text-red-400 text-xs mb-3">{error}</p>}

      {result && (
        <div className="space-y-4">
          {/* Win probability bar */}
          <div>
            <div className="flex justify-between mb-1.5">
              <div className="text-center">
                <p className="font-display text-lg font-bold tabular-nums" style={{ color: c1 }}>
                  {homePct.toFixed(1)}%
                </p>
                <p className="text-[10px] text-text-muted font-display uppercase">{result.home_team_abbr} Win</p>
              </div>
              <div className="text-center">
                <p className="font-display text-xs text-text-muted mt-1">
                  {result.n_simulations.toLocaleString()} sims
                </p>
              </div>
              <div className="text-center">
                <p className="font-display text-lg font-bold tabular-nums" style={{ color: c2 }}>
                  {awayPct.toFixed(1)}%
                </p>
                <p className="text-[10px] text-text-muted font-display uppercase">{result.away_team_abbr} Win</p>
              </div>
            </div>
            <div className="flex h-3 rounded-sm overflow-hidden">
              <div className="transition-all duration-700" style={{ width: `${homePct}%`, backgroundColor: c1 }} />
              <div className="transition-all duration-700" style={{ width: `${awayPct}%`, backgroundColor: c2 }} />
            </div>
          </div>

          {/* Score distribution */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-md bg-surface-800 p-3 text-center border border-border">
              <p className="font-display text-xl font-bold tabular-nums" style={{ color: c1 }}>
                {result.avg_home_score.toFixed(1)}
              </p>
              <p className="text-[10px] text-text-muted font-display uppercase mt-0.5">
                {result.home_team_abbr} Avg Score
              </p>
              <p className="text-[9px] text-text-muted mt-1">
                ±{result.std_home_score.toFixed(1)} pts std dev
              </p>
            </div>
            <div className="rounded-md bg-surface-800 p-3 text-center border border-border">
              <p className="font-display text-xl font-bold tabular-nums" style={{ color: c2 }}>
                {result.avg_away_score.toFixed(1)}
              </p>
              <p className="text-[10px] text-text-muted font-display uppercase mt-0.5">
                {result.away_team_abbr} Avg Score
              </p>
              <p className="text-[9px] text-text-muted mt-1">
                ±{result.std_away_score.toFixed(1)} pts std dev
              </p>
            </div>
          </div>

          {/* Implied total */}
          <div className="flex items-center justify-between px-1">
            <span className="text-[10px] text-text-muted font-display uppercase tracking-wider">Implied Total</span>
            <span className="font-display text-sm font-bold text-text-primary tabular-nums">
              {(result.avg_home_score + result.avg_away_score).toFixed(1)} pts
            </span>
            <span className="text-[10px] text-text-muted font-display uppercase tracking-wider">
              {result.home_wins.toLocaleString()}–{result.away_wins.toLocaleString()}
            </span>
          </div>
        </div>
      )}

      {!result && !loading && (
        <p className="text-[11px] text-text-muted text-center py-3">
          Run N simulated games to see projected win distribution and scores.
        </p>
      )}
    </div>
  );
}

// ── Compare Body ──────────────────────────────────────────────────────────────

function CompareBody({ t1, t2 }: { t1: string; t2: string }) {
  const { data: p1, loading: l1 } = useTeamProfile(t1);
  const { data: p2, loading: l2 } = useTeamProfile(t2);
  const { data: m1, loading: ml1 } = useTeamMetrics(t1);
  const { data: m2, loading: ml2 } = useTeamMetrics(t2);
  const { data: h2h, loading: hl } = useH2H(t1, t2, 10);

  if (l1 || l2 || ml1 || ml2) return <Spinner text="Loading comparison..." />;
  if (!p1 || !p2) return null;

  const c1 = getTeamColors(t1).primary;
  const c2 = getTeamColors(t2).primary;
  const a1 = p1.all_time;
  const a2 = p2.all_time;

  const bars: { label: string; v1: number; v2: number; fmt?: (n: number) => string }[] = [
    { label: 'Win %',      v1: a1.win_pct,          v2: a2.win_pct,          fmt: (n) => `${(n * 100).toFixed(1)}%` },
    { label: 'PPG',        v1: a1.ppg,              v2: a2.ppg,              fmt: (n) => n.toFixed(1) },
    { label: 'Pts Allowed',v1: a1.papg,             v2: a2.papg,             fmt: (n) => n.toFixed(1) },
    { label: 'Point Diff', v1: a1.point_differential, v2: a2.point_differential, fmt: (n) => `${n > 0 ? '+' : ''}${n}` },
  ];

  if (m1 && m2) {
    bars.push(
      { label: 'SOS',       v1: m1.strength_of_schedule, v2: m2.strength_of_schedule, fmt: (n) => `.${(n * 1000).toFixed(0).padStart(3, '0')}` },
      { label: 'Home Win%', v1: m1.home_win_pct,         v2: m2.home_win_pct,         fmt: (n) => `${(n * 100).toFixed(0)}%` },
      { label: 'Away Win%', v1: m1.away_win_pct,         v2: m2.away_win_pct,         fmt: (n) => `${(n * 100).toFixed(0)}%` },
      { label: 'Rec. Form', v1: m1.recent_win_pct,       v2: m2.recent_win_pct,       fmt: (n) => `${(n * 100).toFixed(0)}%` },
    );
  }

  return (
    <div className="space-y-6 animate-fade-up stagger-2">
      {/* Team headers */}
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-3">
          <TeamLogo abbr={t1} size={40} className="rounded-md" />
          <span className="font-display text-lg font-semibold text-text-primary">{p1.team_name}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-display text-lg font-semibold text-text-primary">{p2.team_name}</span>
          <TeamLogo abbr={t2} size={40} className="rounded-md" />
        </div>
      </div>

      {/* Tug-of-war bars */}
      <div className="rounded-lg border border-border bg-surface-850 p-5 space-y-4">
        {bars.map((b) => (
          <TugBar key={b.label} label={b.label} v1={b.v1} v2={b.v2} c1={c1} c2={c2} fmt={b.fmt} />
        ))}
      </div>

      {/* Radar Chart */}
      {m1 && m2 && (
        <TeamRadar m1={m1} m2={m2} t1={t1} t2={t2} c1={c1} c2={c2} />
      )}

      {/* Quick Predict */}
      <QuickPredict t1={t1} t2={t2} c1={c1} c2={c2} />

      {/* Monte Carlo Simulator */}
      <MonteCarloPanel t1={t1} t2={t2} c1={c1} c2={c2} />

      {/* H2H summary + timeline */}
      {!hl && h2h && h2h.total_games > 0 && (
        <>
          <div className="rounded-lg border border-border bg-surface-850 p-5">
            <h3 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em] mb-4">
              Head-to-Head &middot; Last {h2h.total_games}
            </h3>
            <div className="flex items-center gap-4 mb-2">
              <span className="font-display text-xl font-bold tabular-nums" style={{ color: c1 }}>
                {h2h.team1_abbr} {h2h.team1_wins}
              </span>
              <div className="flex-1" />
              <span className="font-display text-xl font-bold tabular-nums" style={{ color: c2 }}>
                {h2h.team2_wins} {h2h.team2_abbr}
              </span>
            </div>
            <div className="flex h-2.5 rounded-sm overflow-hidden">
              <div className="transition-all duration-700"
                style={{ width: `${h2h.total_games > 0 ? ((h2h.team1_wins / h2h.total_games) * 100) : 50}%`, backgroundColor: c1 }} />
              <div className="transition-all duration-700"
                style={{ width: `${h2h.total_games > 0 ? ((h2h.team2_wins / h2h.total_games) * 100) : 50}%`, backgroundColor: c2 }} />
            </div>
            {h2h.ties > 0 && <p className="text-[11px] text-text-muted text-center mt-1">{h2h.ties} tie{h2h.ties > 1 ? 's' : ''}</p>}
          </div>

          {/* H2H Timeline */}
          <H2HTimeline h2h={h2h} t1={t1} t2={t2} c1={c1} c2={c2} />
        </>
      )}

      {/* Schedule Difficulty */}
      <div className="rounded-lg border border-border bg-surface-850 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em]">
            Upcoming Schedule
          </h3>
          <div className="flex items-center gap-2 text-[9px] text-text-muted font-display">
            <span className="px-1.5 py-0.5 rounded bg-win/15 text-win">easy</span>
            <span className="px-1.5 py-0.5 rounded bg-yellow-500/15 text-yellow-400">medium</span>
            <span className="px-1.5 py-0.5 rounded bg-loss/15 text-loss">hard</span>
          </div>
        </div>
        <div className="flex gap-6">
          <ScheduleColumn abbr={t1} color={c1} season={2025} />
          <ScheduleColumn abbr={t2} color={c2} season={2025} />
        </div>
      </div>
    </div>
  );
}

function TugBar({
  label, v1, v2, c1, c2, fmt,
}: {
  label: string; v1: number; v2: number; c1: string; c2: string; fmt?: (n: number) => string;
}) {
  const f = fmt ?? ((n: number) => String(n));
  const abs1 = Math.abs(v1), abs2 = Math.abs(v2);
  const total = abs1 + abs2;
  const pct1 = total > 0 ? (abs1 / total) * 100 : 50;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-semibold tabular-nums" style={{ color: c1 }}>{f(v1)}</span>
        <span className="text-[10px] text-text-muted uppercase tracking-wider font-display font-medium">{label}</span>
        <span className="text-sm font-semibold tabular-nums" style={{ color: c2 }}>{f(v2)}</span>
      </div>
      <div className="flex h-2 rounded-sm overflow-hidden bg-surface-700">
        <div className="transition-all duration-500" style={{ width: `${pct1}%`, backgroundColor: c1 }} />
        <div className="transition-all duration-500" style={{ width: `${100 - pct1}%`, backgroundColor: c2 }} />
      </div>
    </div>
  );
}
