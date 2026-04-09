import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTeams, useTeamProfile, useTeamMetrics, useH2H } from '../hooks/useApi';
import TeamSelector from '../components/TeamSelector';
import Spinner from '../components/Spinner';
import { getTeamColors } from '../theme/teamColors';

export default function Compare() {
  const { team1: paramT1, team2: paramT2 } = useParams<{ team1?: string; team2?: string }>();
  const navigate = useNavigate();
  const { data: teamList } = useTeams();

  const [t1, setT1] = useState(paramT1 ?? '');
  const [t2, setT2] = useState(paramT2 ?? '');

  useEffect(() => { if (paramT1) setT1(paramT1); }, [paramT1]);
  useEffect(() => { if (paramT2) setT2(paramT2); }, [paramT2]);

  // Update URL when teams change
  useEffect(() => {
    if (t1 && t2) {
      navigate(`/compare/${t1}/${t2}`, { replace: true });
    }
  }, [t1, t2, navigate]);

  const bothSelected = !!(t1 && t2 && t1 !== t2);

  return (
    <div>
      {/* Header */}
      <div className="mb-8 animate-fade-up">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-px w-6 bg-accent" />
          <span className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold">
            Side by Side
          </span>
        </div>
        <h1 className="font-display text-3xl font-bold text-text-primary uppercase tracking-tight">
          Compare
        </h1>
      </div>

      {/* Team selectors */}
      <div className="rounded-lg border border-border bg-surface-850 p-6 mb-8 animate-fade-up stagger-1">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-5 items-end">
          <TeamSelector
            teams={teamList?.teams ?? []}
            value={t1}
            onChange={setT1}
            label="Team 1"
            excludeAbbr={t2}
          />
          <div className="font-display text-text-muted text-xl font-bold self-center pt-5 hidden md:block">
            vs
          </div>
          <TeamSelector
            teams={teamList?.teams ?? []}
            value={t2}
            onChange={setT2}
            label="Team 2"
            excludeAbbr={t1}
          />
        </div>
      </div>

      {bothSelected && <CompareBody t1={t1} t2={t2} />}
    </div>
  );
}

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
    { label: 'Win %', v1: a1.win_pct, v2: a2.win_pct, fmt: (n) => `${(n * 100).toFixed(1)}%` },
    { label: 'PPG', v1: a1.ppg, v2: a2.ppg, fmt: (n) => n.toFixed(1) },
    { label: 'Pts Allowed', v1: a1.papg, v2: a2.papg, fmt: (n) => n.toFixed(1) },
    { label: 'Point Diff', v1: a1.point_differential, v2: a2.point_differential, fmt: (n) => `${n > 0 ? '+' : ''}${n}` },
  ];

  if (m1 && m2) {
    bars.push(
      { label: 'SOS', v1: m1.strength_of_schedule, v2: m2.strength_of_schedule, fmt: (n) => `.${(n * 1000).toFixed(0).padStart(3, '0')}` },
      { label: 'Home Win%', v1: m1.home_win_pct, v2: m2.home_win_pct, fmt: (n) => `${(n * 100).toFixed(0)}%` },
      { label: 'Away Win%', v1: m1.away_win_pct, v2: m2.away_win_pct, fmt: (n) => `${(n * 100).toFixed(0)}%` },
      { label: 'Recent Form', v1: m1.recent_win_pct, v2: m2.recent_win_pct, fmt: (n) => `${(n * 100).toFixed(0)}%` },
    );
  }

  return (
    <div className="space-y-6 animate-fade-up stagger-2">
      {/* Team headers */}
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md flex items-center justify-center text-white text-sm font-display font-bold" style={{ backgroundColor: c1 }}>
            {t1}
          </div>
          <span className="font-display text-lg font-semibold text-text-primary">{p1.team_name}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-display text-lg font-semibold text-text-primary">{p2.team_name}</span>
          <div className="w-10 h-10 rounded-md flex items-center justify-center text-white text-sm font-display font-bold" style={{ backgroundColor: c2 }}>
            {t2}
          </div>
        </div>
      </div>

      {/* Tug-of-war bars */}
      <div className="rounded-lg border border-border bg-surface-850 p-5 space-y-4">
        {bars.map((b) => (
          <TugBar key={b.label} label={b.label} v1={b.v1} v2={b.v2} c1={c1} c2={c2} fmt={b.fmt} />
        ))}
      </div>

      {/* H2H */}
      {!hl && h2h && h2h.total_games > 0 && (
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
            <div
              className="transition-all duration-700"
              style={{
                width: `${h2h.total_games > 0 ? ((h2h.team1_wins / h2h.total_games) * 100) : 50}%`,
                backgroundColor: c1,
              }}
            />
            <div
              className="transition-all duration-700"
              style={{
                width: `${h2h.total_games > 0 ? ((h2h.team2_wins / h2h.total_games) * 100) : 50}%`,
                backgroundColor: c2,
              }}
            />
          </div>
          {h2h.ties > 0 && (
            <p className="text-[11px] text-text-muted text-center mt-1">{h2h.ties} tie{h2h.ties > 1 ? 's' : ''}</p>
          )}
        </div>
      )}
    </div>
  );
}

function TugBar({
  label, v1, v2, c1, c2, fmt,
}: {
  label: string; v1: number; v2: number; c1: string; c2: string; fmt?: (n: number) => string;
}) {
  const f = fmt ?? ((n: number) => String(n));
  // Normalize to percentages for bar width
  const abs1 = Math.abs(v1);
  const abs2 = Math.abs(v2);
  const total = abs1 + abs2;
  const pct1 = total > 0 ? (abs1 / total) * 100 : 50;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-semibold tabular-nums" style={{ color: c1 }}>
          {f(v1)}
        </span>
        <span className="text-[10px] text-text-muted uppercase tracking-wider font-display font-medium">
          {label}
        </span>
        <span className="text-sm font-semibold tabular-nums" style={{ color: c2 }}>
          {f(v2)}
        </span>
      </div>
      <div className="flex h-2 rounded-sm overflow-hidden bg-surface-700">
        <div className="transition-all duration-500" style={{ width: `${pct1}%`, backgroundColor: c1 }} />
        <div className="transition-all duration-500" style={{ width: `${100 - pct1}%`, backgroundColor: c2 }} />
      </div>
    </div>
  );
}
