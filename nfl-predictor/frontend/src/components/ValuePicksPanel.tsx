import { useValuePicks } from '../hooks/useApi';
import { getTeamColors } from '../theme/teamColors';
import type { ValuePick } from '../api/types';

// ── helpers ──────────────────────────────────────────────────────────────────

function pct(v: number) {
  return `${Math.round(v * 100)}%`;
}

function edgePp(v: number) {
  const pp = Math.abs(Math.round(v * 100));
  return `${pp}pp`;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

// ── sub-components ───────────────────────────────────────────────────────────

function ConfidenceBadge({ level }: { level: string }) {
  const cls =
    level === 'HIGH'
      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
      : level === 'MEDIUM'
      ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
      : 'bg-slate-500/20 text-slate-400 border-slate-500/30';
  return (
    <span className={`text-[10px] font-bold tracking-widest uppercase px-2 py-0.5 rounded border ${cls}`}>
      {level}
    </span>
  );
}

function ProbBar({
  label,
  prob,
  color,
  muted,
}: {
  label: string;
  prob: number;
  color: string;
  muted?: boolean;
}) {
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px] font-semibold tracking-wider uppercase text-slate-400">{label}</span>
        <span className={`text-sm font-bold tabular-nums ${muted ? 'text-slate-400' : 'text-white'}`}>
          {pct(prob)}
        </span>
      </div>
      <div className="h-2 rounded-full bg-white/5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: pct(prob),
            background: muted ? 'rgba(148,163,184,0.45)' : color,
            boxShadow: muted ? 'none' : `0 0 8px ${color}55`,
          }}
        />
      </div>
    </div>
  );
}

function EdgeBadge({ pick }: { pick: ValuePick }) {
  const favoredTeam = pick.edge_side === 'home' ? pick.home_team : pick.away_team;
  const isPositive = pick.edge > 0;
  const colors = isPositive
    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25'
    : 'bg-orange-500/15 text-orange-300 border-orange-500/25';
  const arrow = isPositive ? '↑' : '↓';
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${colors}`}
    >
      <span>{arrow}</span>
      <span>{edgePp(pick.edge)} on {favoredTeam}</span>
    </span>
  );
}

function SpreadPill({ spread }: { spread: number | null }) {
  if (spread === null) return null;
  const label = spread === 0 ? 'PK' : spread > 0 ? `+${spread}` : `${spread}`;
  return (
    <span className="text-[11px] font-mono text-slate-500 bg-white/5 px-2 py-0.5 rounded">
      {label}
    </span>
  );
}

function PickCard({ pick }: { pick: ValuePick }) {
  const homeColors = getTeamColors(pick.home_team);
  const awayColors = getTeamColors(pick.away_team);
  const edgeTeam = pick.edge_side === 'home' ? pick.home_team : pick.away_team;
  const edgeColor = getTeamColors(edgeTeam).primary;

  return (
    <div
      className="relative rounded-xl border border-white/8 overflow-hidden"
      style={{
        background: 'rgba(15,20,40,0.7)',
        boxShadow: `0 0 0 1px rgba(255,255,255,0.04), inset 0 1px 0 rgba(255,255,255,0.06)`,
      }}
    >
      {/* accent strip — color of the edge-favored team */}
      <div
        className="absolute left-0 top-0 bottom-0 w-0.5 rounded-l-xl"
        style={{ background: edgeColor }}
      />

      <div className="px-5 pt-4 pb-4 pl-6">
        {/* header row: matchup + date + spread + confidence */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            {/* away */}
            <span
              className="text-base font-extrabold tracking-tight"
              style={{ color: awayColors.primary === '#000000' ? '#94a3b8' : awayColors.primary }}
            >
              {pick.away_team}
            </span>
            <span className="text-slate-600 font-light">@</span>
            {/* home */}
            <span
              className="text-base font-extrabold tracking-tight"
              style={{ color: homeColors.primary === '#000000' ? '#94a3b8' : homeColors.primary }}
            >
              {pick.home_team}
            </span>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <SpreadPill spread={pick.vegas_spread} />
            <span className="text-[11px] text-slate-500">{formatDate(pick.game_date)}</span>
            <ConfidenceBadge level={pick.model_confidence} />
          </div>
        </div>

        {/* probability bars */}
        <div className="flex gap-4 mb-3.5">
          <ProbBar
            label="Model"
            prob={pick.model_home_prob}
            color={homeColors.primary}
          />
          <ProbBar
            label="Vegas"
            prob={pick.vegas_home_implied_prob}
            color="#64748b"
            muted
          />
        </div>

        {/* edge badge + small label */}
        <div className="flex items-center justify-between">
          <EdgeBadge pick={pick} />
          <span className="text-[11px] text-slate-600">home win probability</span>
        </div>
      </div>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export default function ValuePicksPanel() {
  const { data, loading, error } = useValuePicks();

  return (
    <section className="w-full">
      {/* section header */}
      <div className="mb-4">
        <h2 className="text-xl font-bold text-white tracking-tight">
          Value Picks — Model vs Vegas
        </h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Games where our model disagrees with Vegas by ≥ 4pp
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-8 text-slate-500 text-sm">
          <div className="h-4 w-4 rounded-full border-2 border-slate-600 border-t-blue-400 animate-spin" />
          Scanning upcoming lines…
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {data && data.picks.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
          <div className="text-3xl select-none">✓</div>
          <p className="text-slate-400 text-sm max-w-xs">
            No mispriced games this week — model and Vegas agree on all matchups.
          </p>
          {data.note && <p className="text-slate-600 text-xs">{data.note}</p>}
        </div>
      )}

      {data && data.picks.length > 0 && (
        <>
          <div className="flex flex-col gap-3">
            {data.picks.map((pick, i) => (
              <div
                key={pick.game_id}
                className="stagger-item"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <PickCard pick={pick} />
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-600 mt-3 text-right">{data.note}</p>
        </>
      )}
    </section>
  );
}
