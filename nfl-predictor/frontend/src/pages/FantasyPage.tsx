import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { api } from '../api/client';
import type {
  FantasyLeaderboard, FantasyPlayerEntry, FantasyProjection,
  DraftRanking, TradeAnalysis, TradePlayer, PlayerSearchResult,
  PowerRanking, TradeValue, RosterMatchEntry,
} from '../api/types';
import Spinner from '../components/Spinner';
import DataBadge from '../components/DataBadge';

// ── Shared helpers ────────────────────────────────────────────────────────────

const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE', 'K'] as const;
type PositionFilter = typeof POSITIONS[number];

function posColor(pos: string | null): string {
  switch (pos) {
    case 'QB': return '#e74c3c';
    case 'RB': return '#27ae60';
    case 'WR': return '#2980b9';
    case 'TE': return '#8e44ad';
    case 'K':  return '#f39c12';
    default:   return '#888';
  }
}

function matchupColor(score: number): string {
  if (score >= 1.1) return 'var(--color-win)';
  if (score <= 0.9) return 'var(--color-loss)';
  return 'var(--color-text-muted)';
}

function PosBadge({ pos }: { pos: string | null }) {
  return (
    <span
      className="text-[9px] font-display font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
      style={{ backgroundColor: `${posColor(pos)}22`, color: posColor(pos) }}
    >
      {pos ?? '—'}
    </span>
  );
}

// Inline tooltip for matchup score / confidence
function MTooltip({ text, children }: { text: string; children: React.ReactNode }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-50 w-64 rounded-lg border border-border bg-surface-800 px-2.5 py-2 text-[10px] text-text-secondary shadow-xl pointer-events-none" style={{ whiteSpace: 'normal' }}>
          {text}
        </span>
      )}
    </span>
  );
}

function ConfBadge({ conf }: { conf: string }) {
  const style = conf === 'high' ? 'bg-win/15 text-win' : conf === 'low' ? 'bg-loss/15 text-loss' : 'bg-yellow-500/15 text-yellow-400';
  return <span className={`text-[9px] font-display font-bold uppercase px-1.5 py-0.5 rounded ${style}`}>{conf}</span>;
}

function MLBadge({ projection }: { projection: FantasyProjection }) {
  const contribs = projection.contributions ?? [];
  const top = contribs.slice(0, 3);
  const tip = top.length === 0
    ? `ML model ${projection.model_version ?? ''} — floor ${projection.floor_ppr?.toFixed(1) ?? '—'} / ceiling ${projection.ceiling_ppr?.toFixed(1) ?? '—'} PPR`
    : `ML ${projection.model_version ?? ''} top drivers: ${top.map((c) => `${c.direction === 'up' ? '↑' : c.direction === 'down' ? '↓' : '·'}${c.label} ${c.shap_value >= 0 ? '+' : ''}${c.shap_value.toFixed(2)}`).join(' · ')}`;
  return (
    <MTooltip text={tip}>
      <span className="text-[9px] font-display font-bold uppercase px-1.5 py-0.5 rounded bg-accent/15 text-accent">
        ML
      </span>
    </MTooltip>
  );
}

function Headshot({ url, name }: { url: string | null; name: string }) {
  return url ? (
    <img
      src={url}
      alt={name}
      className="w-8 h-8 rounded-full object-cover bg-surface-700 shrink-0"
      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
    />
  ) : (
    <div className="w-8 h-8 rounded-full bg-surface-700 shrink-0 flex items-center justify-center">
      <span className="text-[9px] text-text-muted font-bold">{name.slice(0, 2).toUpperCase()}</span>
    </div>
  );
}

function PositionFilter({
  value, onChange,
}: { value: PositionFilter; onChange: (p: PositionFilter) => void }) {
  return (
    <div className="flex gap-1">
      {POSITIONS.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`px-3 py-1 rounded text-[11px] font-display font-semibold uppercase tracking-wide transition-colors ${
            value === p
              ? 'bg-accent text-surface-900'
              : 'bg-surface-800 text-text-muted hover:text-text-secondary border border-border'
          }`}
        >
          {p}
        </button>
      ))}
    </div>
  );
}

function ScoringToggle({
  value, onChange,
}: { value: string; onChange: (s: string) => void }) {
  return (
    <div className="flex gap-1">
      {(['ppr', 'standard'] as const).map((s) => (
        <button
          key={s}
          onClick={() => onChange(s)}
          className={`px-3 py-1 rounded text-[11px] font-display font-semibold uppercase tracking-wide transition-colors ${
            value === s
              ? 'bg-accent text-surface-900'
              : 'bg-surface-800 text-text-muted hover:text-text-secondary border border-border'
          }`}
        >
          {s === 'ppr' ? 'PPR' : 'STD'}
        </button>
      ))}
    </div>
  );
}

// ── Tab: Dashboard ────────────────────────────────────────────────────────────

const DASH_POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const;

function DashboardTab() {
  const [week, setWeek] = useState(1);
  const [season] = useState(2024);
  const [projections, setProjections] = useState<Record<string, FantasyProjection[]>>({});
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async (w: number) => {
    setLoading(true);
    try {
      const results = await Promise.all(
        DASH_POSITIONS.map((pos) => api.getFantasyProjections(w, season, pos, 'ppr'))
      );
      const map: Record<string, FantasyProjection[]> = {};
      DASH_POSITIONS.forEach((pos, i) => {
        map[pos] = results[i].slice(0, 5);
      });
      setProjections(map);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [season]);

  useEffect(() => { load(week); }, [week, load]);

  return (
    <div className="space-y-6">
      {/* Info banner */}
      <div className="rounded-xl border border-border bg-surface-800/50 px-4 py-3 flex items-center gap-3 flex-wrap">
        <span className="text-[11px] text-text-muted">
          Projections: season avg adjusted for matchup, injury status &amp; weather.
        </span>
        <div className="flex items-center gap-2 ml-auto">
          <DataBadge source="espn" />
          <DataBadge source="pfr" />
          <DataBadge source="open-meteo" />
          <DataBadge source="calculated" />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <label className="text-xs text-text-muted font-display uppercase tracking-widest">Week</label>
        <select
          value={week}
          onChange={(e) => setWeek(Number(e.target.value))}
          className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
        >
          {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
            <option key={w} value={w}>Week {w}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <Spinner text="Generating projections…" />
      ) : (
        <div className="grid grid-cols-2 gap-6">
          {DASH_POSITIONS.map((pos) => {
            const data = projections[pos] ?? [];
            return (
              <div key={pos} className="rounded-xl border border-border bg-surface-850 p-5">
                <div className="flex items-center gap-2 mb-4">
                  <PosBadge pos={pos} />
                  <span className="text-[11px] font-display uppercase tracking-widest text-text-muted">
                    Top 5 Week {week}
                  </span>
                </div>
                {data.length === 0 ? (
                  <p className="text-xs text-text-muted py-4 text-center">No projections available</p>
                ) : (
                  <>
                    <ResponsiveContainer width="100%" height={160}>
                      <BarChart data={data} layout="vertical" margin={{ left: 80, right: 24, top: 0, bottom: 0 }}>
                        <XAxis type="number" hide />
                        <YAxis
                          type="category"
                          dataKey="full_name"
                          tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
                          width={80}
                          tickFormatter={(v: string) => v.split(' ').pop() ?? v}
                        />
                        <Tooltip
                          contentStyle={{ background: 'var(--color-surface-800)', border: '1px solid var(--color-border)', borderRadius: 8 }}
                          formatter={(val) => [`${(val as number).toFixed(1)} pts`, 'Projected']}
                        />
                        <Bar dataKey="projected_points_ppr" radius={[0, 4, 4, 0]}>
                          {data.map((_, idx) => (
                            <Cell key={idx} fill={posColor(pos)} opacity={1 - idx * 0.12} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                    <div className="mt-3 space-y-1">
                      {data.map((p, i) => (
                        <button
                          key={p.player_id}
                          onClick={() => navigate(`/players/${p.player_id}`)}
                          className="w-full flex items-center gap-2 px-2 py-1 rounded hover:bg-surface-800 transition-colors text-left"
                        >
                          <span className="text-[10px] text-text-muted w-4 shrink-0">{i + 1}</span>
                          <Headshot url={p.headshot_url} name={p.full_name} />
                          <span className="flex-1 text-xs text-text-secondary truncate">{p.full_name}</span>
                          {p.model_source === 'ml' && <MLBadge projection={p} />}
                          <MTooltip text={`${p.confidence === 'low' ? `Low confidence — ${p.injury_status ?? 'limited data'}` : p.confidence === 'high' ? 'Full stats, no injury concerns' : 'Based on season average'}`}>
                            <ConfBadge conf={p.confidence} />
                          </MTooltip>
                          <span className="text-xs font-bold tabular-nums" style={{ color: posColor(pos) }}>
                            {p.projected_points_ppr.toFixed(1)}
                          </span>
                          {p.floor_ppr !== null && p.ceiling_ppr !== null && (
                            <span className="text-[9px] text-text-muted tabular-nums whitespace-nowrap">
                              {p.floor_ppr.toFixed(1)}–{p.ceiling_ppr.toFixed(1)}
                            </span>
                          )}
                          {p.matchup_score !== 1.0 && (
                            <MTooltip text={`Matchup Score: ${p.matchup_score.toFixed(2)}× — opponent defensive advanced stats proxy. >1.1 = favorable, <0.9 = unfavorable, 1.0 = neutral`}>
                              <span className="text-[10px]" style={{ color: matchupColor(p.matchup_score) }}>
                                ×{p.matchup_score.toFixed(2)}
                              </span>
                            </MTooltip>
                          )}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Tab: Leaderboards ─────────────────────────────────────────────────────────

function LeaderboardsTab() {
  const [position, setPosition] = useState<PositionFilter>('QB');
  const [scoring, setScoring] = useState('ppr');
  const [season] = useState(2024);
  const [data, setData] = useState<FantasyLeaderboard | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    api.getFantasyTop(position === 'ALL' ? undefined : position, season, scoring, 50)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [position, scoring, season]);

  const players: FantasyPlayerEntry[] = data?.players ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 flex-wrap">
        <PositionFilter value={position} onChange={setPosition} />
        <ScoringToggle value={scoring} onChange={setScoring} />
      </div>

      {loading ? <Spinner text="Loading leaderboard…" /> : (
        <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {['#', 'Player', 'Team', 'Pos', 'Season Pts', 'Avg/Gm'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-display uppercase tracking-widest text-text-muted">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {players.map((p, i) => (
                <tr
                  key={p.player_id}
                  onClick={() => navigate(`/players/${p.player_id}`)}
                  className="border-b border-border/50 hover:bg-surface-800 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-2.5 text-text-muted text-[11px]">{i + 1}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <Headshot url={p.headshot_url} name={p.full_name} />
                      <span className="text-text-primary font-medium text-xs">{p.full_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-text-muted text-xs">{p.team_abbr ?? '—'}</td>
                  <td className="px-4 py-2.5"><PosBadge pos={p.position} /></td>
                  <td className="px-4 py-2.5 font-bold tabular-nums text-text-primary text-sm">
                    {scoring === 'ppr'
                      ? p.fantasy_points_ppr.toFixed(1)
                      : p.fantasy_points_standard.toFixed(1)}
                  </td>
                  <td className="px-4 py-2.5 text-text-secondary tabular-nums text-xs">
                    {p.points_per_game_ppr.toFixed(1)}
                  </td>
                </tr>
              ))}
              {!loading && players.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-text-muted text-xs">
                    No data — run scripts/import_rosters.py to populate player stats.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Tab: Waiver Wire ──────────────────────────────────────────────────────────

function WaiverTab() {
  const [week, setWeek] = useState(1);
  const [season] = useState(2024);
  const [position, setPosition] = useState<PositionFilter>('ALL');
  const [players, setPlayers] = useState<FantasyProjection[]>([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    api.getWaiverWire(week, season, 'ppr', position === 'ALL' ? 'all' : position, 30)
      .then(setPlayers)
      .catch(() => setPlayers([]))
      .finally(() => setLoading(false));
  }, [week, season, position]);

  function oppBar(score: number) {
    const pct = Math.round(score * 10);
    const color = score > 7 ? 'var(--color-win)' : score > 4 ? '#f39c12' : 'var(--color-loss)';
    return (
      <div className="flex items-center gap-1.5">
        <div className="w-16 h-1.5 rounded-full bg-surface-700 overflow-hidden">
          <div className="h-full rounded-full transition-all" style={{ width: `${pct}0%`, backgroundColor: color }} />
        </div>
        <span className="text-[10px] tabular-nums" style={{ color }}>{score.toFixed(1)}</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted font-display uppercase tracking-widest">Week</label>
          <select
            value={week}
            onChange={(e) => setWeek(Number(e.target.value))}
            className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
          >
            {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
              <option key={w} value={w}>Week {w}</option>
            ))}
          </select>
        </div>
        <PositionFilter value={position} onChange={setPosition} />
      </div>

      {loading ? <Spinner text="Loading waiver wire…" /> : (
        <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {['#', 'Player', 'Pos', 'Team', 'Proj Pts', 'Opportunity', 'Matchup', 'Status'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-display uppercase tracking-widest text-text-muted">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {players.map((p, i) => (
                <tr
                  key={p.player_id}
                  onClick={() => navigate(`/players/${p.player_id}`)}
                  className="border-b border-border/50 hover:bg-surface-800 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-2.5 text-text-muted text-[11px]">{i + 1}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <Headshot url={p.headshot_url} name={p.full_name} />
                      <span className="text-text-primary font-medium text-xs truncate max-w-[120px]">{p.full_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5"><PosBadge pos={p.position} /></td>
                  <td className="px-4 py-2.5 text-text-muted text-xs">{p.team_abbr ?? '—'}</td>
                  <td className="px-4 py-2.5 font-bold tabular-nums text-text-primary">
                    {p.projected_points_ppr.toFixed(1)}
                  </td>
                  <td className="px-4 py-2.5">{oppBar(p.opportunity_score)}</td>
                  <td className="px-4 py-2.5">
                    <MTooltip text={`Matchup Score: ${p.matchup_score.toFixed(2)}× — Week ${week} opponent defensive stats. >1.1 = favorable, <0.9 = unfavorable, 1.0 = neutral`}>
                      <span className="text-xs tabular-nums font-medium cursor-help" style={{ color: matchupColor(p.matchup_score) }}>
                        {p.matchup_score.toFixed(2)}×
                      </span>
                    </MTooltip>
                  </td>
                  <td className="px-4 py-2.5">
                    {p.injury_status ? (
                      <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                        ['Out', 'IR', 'PUP'].includes(p.injury_status)
                          ? 'bg-loss/15 text-loss'
                          : 'bg-yellow-500/15 text-yellow-400'
                      }`}>
                        {p.injury_status}
                      </span>
                    ) : (
                      <span className="text-[10px] text-text-muted">Active</span>
                    )}
                  </td>
                </tr>
              ))}
              {!loading && players.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-text-muted text-xs">
                    No waiver data — run scripts/import_rosters.py first.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Tab: Draft ────────────────────────────────────────────────────────────────

function DraftTab() {
  const [season, setSeason] = useState(2025);
  const [scoring, setScoring] = useState('ppr');
  const [position, setPosition] = useState<PositionFilter>('ALL');
  const [search, setSearch] = useState('');
  const [rankings, setRankings] = useState<DraftRanking[]>([]);
  const [loading, setLoading] = useState(false);
  const [mockMode, setMockMode] = useState(false);
  const [drafted, setDrafted] = useState<Set<number>>(new Set());
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    api.getDraftRankings(season, scoring, position === 'ALL' ? 'all' : position)
      .then(setRankings)
      .catch(() => setRankings([]))
      .finally(() => setLoading(false));
  }, [season, scoring, position]);

  const filtered = rankings.filter((r) => {
    if (mockMode && drafted.has(r.player_id)) return false;
    if (search) return r.full_name.toLowerCase().includes(search.toLowerCase());
    return true;
  });

  function toggleDraft(id: number) {
    setDrafted((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  let lastTier = -1;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted font-display uppercase tracking-widest">Season</label>
          <select
            value={season}
            onChange={(e) => setSeason(Number(e.target.value))}
            className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
          >
            {[2023, 2024, 2025].map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <ScoringToggle value={scoring} onChange={setScoring} />
        <PositionFilter value={position} onChange={setPosition} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search player…"
          className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary placeholder:text-text-muted focus:outline-none focus:border-accent w-40"
        />
        <button
          onClick={() => { setMockMode((v) => !v); setDrafted(new Set()); }}
          className={`px-4 py-1.5 rounded text-xs font-display font-semibold uppercase tracking-wide transition-colors border ${
            mockMode ? 'bg-accent text-surface-900 border-accent' : 'border-border text-text-muted hover:text-text-secondary'
          }`}
        >
          {mockMode ? 'Mock Draft ON' : 'Mock Draft'}
        </button>
        {mockMode && (
          <span className="text-xs text-text-muted">{drafted.size} drafted</span>
        )}
      </div>

      {loading ? <Spinner text="Generating draft rankings…" /> : (
        <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {['Rank', 'Tier', 'Player', 'Pos', 'Team', 'ADP', 'Pos Rank', 'Proj Pts'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-display uppercase tracking-widest text-text-muted">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                const tierSep = r.tier !== lastTier;
                lastTier = r.tier;
                return [
                  tierSep && (
                    <tr key={`tier-${r.tier}`}>
                      <td colSpan={8} className="px-4 py-2 bg-surface-900 border-b border-border">
                        <span className="text-[10px] font-display font-bold uppercase tracking-widest text-text-muted">
                          Tier {r.tier}
                        </span>
                      </td>
                    </tr>
                  ),
                  <tr
                    key={r.player_id}
                    onClick={() => mockMode ? toggleDraft(r.player_id) : navigate(`/players/${r.player_id}`)}
                    className={`border-b border-border/50 transition-colors cursor-pointer ${
                      drafted.has(r.player_id)
                        ? 'opacity-30 line-through'
                        : 'hover:bg-surface-800'
                    }`}
                  >
                    <td className="px-4 py-2.5 text-text-muted text-[11px]">{r.overall_rank}</td>
                    <td className="px-4 py-2.5">
                      <span className="text-[9px] font-display font-bold px-1.5 py-0.5 rounded bg-accent/15 text-accent">
                        T{r.tier}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <Headshot url={r.headshot_url} name={r.full_name} />
                        <span className="text-text-primary font-medium text-xs truncate max-w-[120px]">{r.full_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5"><PosBadge pos={r.position} /></td>
                    <td className="px-4 py-2.5 text-text-muted text-xs">{r.team_abbr ?? '—'}</td>
                    <td className="px-4 py-2.5 text-text-secondary tabular-nums text-xs">{r.adp.toFixed(1)}</td>
                    <td className="px-4 py-2.5 text-text-muted tabular-nums text-xs">{r.position} {r.position_rank}</td>
                    <td className="px-4 py-2.5 font-bold tabular-nums text-text-primary">
                      {r.projected_season_points.toFixed(0)}
                    </td>
                  </tr>,
                ];
              })}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-text-muted text-xs">
                    No rankings found. Try a different filter or run scripts/import_rosters.py.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Tab: Trade Analyzer ───────────────────────────────────────────────────────

function PlayerSearchPanel({
  label,
  players,
  onAdd,
  onRemove,
}: {
  label: string;
  players: TradePlayer[];
  onAdd: (p: PlayerSearchResult) => void;
  onRemove: (id: number) => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PlayerSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      if (q.length < 2) { setResults([]); setOpen(false); return; }
      try {
        const r = await api.searchPlayers(q);
        setResults(r.slice(0, 6));
        setOpen(r.length > 0);
      } catch { setResults([]); }
    }, 250);
  }

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  function pick(p: PlayerSearchResult) {
    setQuery('');
    setResults([]);
    setOpen(false);
    onAdd(p);
  }

  return (
    <div className="flex-1 rounded-xl border border-border bg-surface-850 p-5 space-y-4">
      <h3 className="font-display text-[11px] font-bold uppercase tracking-[0.2em] text-text-muted">{label}</h3>

      {/* Player list */}
      <div className="space-y-2 min-h-[60px]">
        {players.map((p) => (
          <div key={p.player_id} className="flex items-center gap-2 group">
            <Headshot url={p.headshot_url} name={p.full_name} />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-text-primary truncate">{p.full_name}</p>
              <p className="text-[10px] text-text-muted">{p.position} · {p.team_abbr ?? '—'}</p>
            </div>
            <span className="text-xs font-bold tabular-nums text-accent">{p.ros_projected.toFixed(1)}</span>
            <button
              onClick={() => onRemove(p.player_id)}
              className="w-5 h-5 rounded flex items-center justify-center text-text-muted hover:text-loss transition-colors opacity-0 group-hover:opacity-100"
            >
              ×
            </button>
          </div>
        ))}
        {players.length === 0 && (
          <p className="text-xs text-text-muted text-center py-4">Add up to 3 players</p>
        )}
      </div>

      {/* Search */}
      {players.length < 3 && (
        <div ref={ref} className="relative">
          <input
            value={query}
            onChange={handleChange}
            onFocus={() => results.length > 0 && setOpen(true)}
            placeholder="Search player to add…"
            className="w-full bg-surface-800 border border-border rounded px-3 py-1.5 text-xs text-text-secondary placeholder:text-text-muted focus:outline-none focus:border-accent"
          />
          {open && results.length > 0 && (
            <div className="absolute top-full mt-1 left-0 right-0 rounded-lg border border-border bg-surface-850 shadow-2xl z-20 overflow-hidden">
              {results.map((r) => (
                <button
                  key={r.player_id}
                  onMouseDown={() => pick(r)}
                  className="w-full flex items-center gap-2 px-3 py-2 hover:bg-surface-800 transition-colors text-left"
                >
                  <Headshot url={r.headshot_url} name={r.full_name} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-text-primary truncate">{r.full_name}</p>
                    <p className="text-[10px] text-text-muted">{r.position} · {r.team_abbr}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TradeTab({ externalWeek }: { externalWeek?: number } = {}) {
  const [internalWeek, setInternalWeek] = useState(1);
  const week = externalWeek ?? internalWeek;
  const [season] = useState(2024);
  const [givePlayers, setGivePlayers] = useState<TradePlayer[]>([]);
  const [getPlayers, setGetPlayers] = useState<TradePlayer[]>([]);
  const [result, setResult] = useState<TradeAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addToGive(p: PlayerSearchResult) {
    if (givePlayers.find((x) => x.player_id === p.player_id)) return;
    setGivePlayers((prev) => [
      ...prev,
      { player_id: p.player_id, full_name: p.full_name, position: p.position,
        team_abbr: p.team_abbr, headshot_url: p.headshot_url, ros_projected: 0 },
    ]);
    setResult(null);
  }

  function addToGet(p: PlayerSearchResult) {
    if (getPlayers.find((x) => x.player_id === p.player_id)) return;
    setGetPlayers((prev) => [
      ...prev,
      { player_id: p.player_id, full_name: p.full_name, position: p.position,
        team_abbr: p.team_abbr, headshot_url: p.headshot_url, ros_projected: 0 },
    ]);
    setResult(null);
  }

  async function analyze() {
    if (!givePlayers.length || !getPlayers.length) {
      setError('Add at least one player to each side.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await api.analyzeTrade({
        give_player_ids: givePlayers.map((p) => p.player_id),
        get_player_ids: getPlayers.map((p) => p.player_id),
        week,
        season,
      });
      setResult(res);
      // Update ros_projected in panels
      setGivePlayers(res.give);
      setGetPlayers(res.get);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  }

  const verdictStyle: Record<string, string> = {
    WIN:  'bg-win/15 text-win border-win/30',
    LOSE: 'bg-loss/15 text-loss border-loss/30',
    FAIR: 'bg-accent/15 text-accent border-accent/30',
  };

  return (
    <div className="space-y-6">
      {externalWeek === undefined && (
        <div className="flex items-center gap-4">
          <label className="text-xs text-text-muted font-display uppercase tracking-widest">Current Week</label>
          <select
            value={internalWeek}
            onChange={(e) => { setInternalWeek(Number(e.target.value)); setResult(null); }}
            className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
          >
            {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
              <option key={w} value={w}>Week {w}</option>
            ))}
          </select>
          <span className="text-xs text-text-muted">ROS = weeks {week}–18</span>
        </div>
      )}

      <div className="flex gap-4">
        <PlayerSearchPanel label="You Give" players={givePlayers} onAdd={addToGive} onRemove={(id) => { setGivePlayers((p) => p.filter((x) => x.player_id !== id)); setResult(null); }} />
        <div className="flex items-center text-text-muted font-display text-xl">⇄</div>
        <PlayerSearchPanel label="You Get" players={getPlayers} onAdd={addToGet} onRemove={(id) => { setGetPlayers((p) => p.filter((x) => x.player_id !== id)); setResult(null); }} />
      </div>

      {error && <p className="text-xs text-loss">{error}</p>}

      <button
        onClick={analyze}
        disabled={loading}
        className="px-6 py-2.5 rounded-lg bg-accent text-surface-900 font-display font-bold text-sm uppercase tracking-widest hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {loading ? 'Analyzing…' : 'Analyze Trade'}
      </button>

      {result && (
        <div className="rounded-xl border border-border bg-surface-850 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-[11px] uppercase tracking-[0.2em] text-text-muted">Trade Verdict</h3>
            <span className={`text-sm font-display font-bold uppercase tracking-widest px-3 py-1 rounded border ${verdictStyle[result.verdict]}`}>
              {result.verdict}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="text-center">
              <p className="text-[10px] text-text-muted font-display uppercase tracking-widest mb-1">You Give</p>
              <p className="text-2xl font-bold tabular-nums text-loss">{result.give_total.toFixed(1)}</p>
              <p className="text-[10px] text-text-muted">projected pts</p>
            </div>
            <div className="text-center">
              <p className="text-[10px] text-text-muted font-display uppercase tracking-widest mb-1">Delta</p>
              <p className={`text-2xl font-bold tabular-nums ${result.delta >= 0 ? 'text-win' : 'text-loss'}`}>
                {result.delta >= 0 ? '+' : ''}{result.delta.toFixed(1)}
              </p>
              <p className="text-[10px] text-text-muted">points</p>
            </div>
            <div className="text-center">
              <p className="text-[10px] text-text-muted font-display uppercase tracking-widest mb-1">You Get</p>
              <p className="text-2xl font-bold tabular-nums text-win">{result.get_total.toFixed(1)}</p>
              <p className="text-[10px] text-text-muted">projected pts</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tab: Power Rankings ───────────────────────────────────────────────────────

function PowerRankingsTab() {
  const [week, setWeek] = useState(1);
  const [season] = useState(2024);
  const [rankings, setRankings] = useState<PowerRanking[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.getFantasyPowerRankings(week, season)
      .then((r) => setRankings(r.rankings))
      .catch(() => setRankings([]))
      .finally(() => setLoading(false));
  }, [week, season]);

  function trendIcon(t: PowerRanking['trend'], change: number) {
    if (t === 'rising')  return <span className="text-win text-xs">▲{Math.abs(change)}</span>;
    if (t === 'falling') return <span className="text-loss text-xs">▼{Math.abs(change)}</span>;
    return <span className="text-text-muted text-xs">–</span>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <label className="text-xs text-text-muted font-display uppercase tracking-widest">Week</label>
        <select value={week} onChange={(e) => setWeek(Number(e.target.value))}
          className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent">
          {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => <option key={w} value={w}>Week {w}</option>)}
        </select>
        <span className="text-xs text-text-muted ml-2">Composite: recent form, pt diff, adv stats, next opp strength</span>
      </div>

      {loading ? <Spinner text="Computing power rankings…" /> : (
        <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {['Rank', 'Trend', 'Team', 'Conf', 'Score', 'Recent', 'Pt Diff', 'Fantasy Implication'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-display uppercase tracking-widest text-text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rankings.map((r) => (
                <tr key={r.team_abbr} className={`border-b border-border/50 hover:bg-surface-800 transition-colors ${r.rank <= 5 ? 'bg-win/3' : r.rank >= 28 ? 'bg-loss/3' : ''}`}>
                  <td className="px-4 py-2.5 font-bold text-text-primary tabular-nums">{r.rank}</td>
                  <td className="px-4 py-2.5">{trendIcon(r.trend, r.rank_change)}</td>
                  <td className="px-4 py-2.5 font-semibold text-text-primary text-xs">{r.team_abbr}</td>
                  <td className="px-4 py-2.5 text-text-muted text-xs">{r.conference}</td>
                  <td className="px-4 py-2.5 tabular-nums text-text-secondary">{(r.composite_score * 100).toFixed(0)}</td>
                  <td className="px-4 py-2.5 tabular-nums text-text-muted text-xs">{r.recent_wins}-{r.recent_games - r.recent_wins}</td>
                  <td className={`px-4 py-2.5 tabular-nums text-xs font-medium ${r.pt_diff_4g > 0 ? 'text-win' : r.pt_diff_4g < 0 ? 'text-loss' : 'text-text-muted'}`}>
                    {r.pt_diff_4g > 0 ? '+' : ''}{r.pt_diff_4g}
                  </td>
                  <td className="px-4 py-2.5 text-[10px] text-text-muted max-w-[200px]">{r.implication}</td>
                </tr>
              ))}
              {!loading && rankings.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-text-muted text-xs">No data — ensure player_season_stats is populated.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Roster Import Helper ──────────────────────────────────────────────────────

function RosterImportHelper({ onImported }: { onImported: (ids: number[]) => void }) {
  const [text, setText] = useState('');
  const [matched, setMatched] = useState<RosterMatchEntry[]>([]);
  const [unmatched, setUnmatched] = useState<string[]>([]);
  const [step, setStep] = useState<'input' | 'confirm'>('input');
  const [loading, setLoading] = useState(false);

  async function handleSearch() {
    const names = text.split('\n').map((n) => n.trim()).filter(Boolean);
    if (!names.length) return;
    setLoading(true);
    try {
      const res = await api.importRosterByNames(names, 2024);
      setMatched(res.matched);
      setUnmatched(res.unmatched);
      setStep('confirm');
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    const ids = matched.map((m) => m.player_id);
    if (!ids.length) return;
    onImported(ids);
  }

  return (
    <div className="rounded-xl border border-border bg-surface-850 p-5 space-y-4">
      <h3 className="font-display text-[11px] font-bold uppercase tracking-[0.2em] text-text-muted">Setup My Roster</h3>
      {step === 'input' ? (
        <>
          <p className="text-xs text-text-muted">Paste your NFL.com roster player names (one per line) to enable Start/Sit recommendations.</p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            placeholder={"Patrick Mahomes\nJustin Jefferson\nChristian McCaffrey"}
            className="w-full bg-surface-800 border border-border rounded px-3 py-2 text-xs text-text-secondary placeholder:text-text-muted focus:outline-none focus:border-accent resize-y font-mono"
          />
          <button onClick={handleSearch} disabled={loading || !text.trim()}
            className="px-5 py-2 rounded-lg bg-accent text-surface-900 font-display font-bold text-xs uppercase tracking-widest hover:opacity-90 disabled:opacity-50 transition-opacity">
            {loading ? 'Searching…' : 'Find Players'}
          </button>
        </>
      ) : (
        <>
          <p className="text-xs text-text-muted">Confirm matched players ({matched.length} found, {unmatched.length} not found):</p>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {matched.map((m) => (
              <div key={m.player_id} className="flex items-center gap-2 text-xs">
                <span className="text-win">✓</span>
                <span className="text-text-primary font-medium">{m.full_name}</span>
                <span className="text-text-muted">{m.position} · {m.team_abbr}</span>
                {m.input_name !== m.full_name && <span className="text-[9px] text-text-muted italic">({m.input_name})</span>}
              </div>
            ))}
            {unmatched.map((n) => (
              <div key={n} className="flex items-center gap-2 text-xs">
                <span className="text-loss">✗</span>
                <span className="text-text-muted line-through">{n}</span>
              </div>
            ))}
          </div>
          <div className="flex gap-3">
            <button onClick={handleConfirm} disabled={!matched.length}
              className="px-5 py-2 rounded-lg bg-accent text-surface-900 font-display font-bold text-xs uppercase tracking-widest hover:opacity-90 disabled:opacity-50">
              Confirm Roster
            </button>
            <button onClick={() => { setStep('input'); setMatched([]); setUnmatched([]); }}
              className="px-4 py-2 rounded-lg border border-border text-text-muted font-display text-xs uppercase tracking-widest hover:text-text-secondary">
              Reset
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ── Trade Value Board sidebar ─────────────────────────────────────────────────

function TradeValueBoard({ week, season }: { week: number; season: number }) {
  const [players, setPlayers] = useState<TradeValue[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    api.getFantasyTradeValues(week, season)
      .then((r) => setPlayers(r.players))
      .catch(() => setPlayers([]))
      .finally(() => setLoading(false));
  }, [open, week, season]);

  function schedColor(s: TradeValue['schedule_difficulty']) {
    return s === 'easy' ? 'text-win' : s === 'hard' ? 'text-loss' : 'text-text-muted';
  }

  return (
    <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
      <button onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-surface-800/50 transition-colors">
        <span className="font-display text-[11px] font-bold uppercase tracking-[0.2em] text-text-muted">ROS Trade Value Board</span>
        <svg className={`w-4 h-4 text-text-muted transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="border-t border-border">
          {loading ? <div className="p-4"><Spinner text="Loading trade values…" /></div> : (
            <div className="overflow-y-auto max-h-80">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-surface-800/30">
                    {['#', 'Player', 'Pos', 'ROS Pts', 'Schedule'].map((h) => (
                      <th key={h} className="px-3 py-2 text-left text-[9px] font-display uppercase tracking-widest text-text-muted">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {players.map((p) => (
                    <tr key={p.player_id} className="border-b border-border/40 hover:bg-surface-800 transition-colors">
                      <td className="px-3 py-2 text-text-muted">{p.rank}</td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1.5">
                          {p.headshot_url && (
                            <img src={p.headshot_url} alt={p.full_name}
                              className="w-5 h-5 rounded-full object-cover shrink-0 bg-surface-700"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                          )}
                          <span className="text-text-primary font-medium truncate max-w-[100px]">{p.full_name}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2"><PosBadge pos={p.position} /></td>
                      <td className="px-3 py-2 font-bold tabular-nums text-text-primary">{p.ros_projected.toFixed(0)}</td>
                      <td className={`px-3 py-2 font-bold uppercase text-[9px] ${schedColor(p.schedule_difficulty)}`}>
                        {p.schedule_difficulty}
                      </td>
                    </tr>
                  ))}
                  {!loading && players.length === 0 && (
                    <tr><td colSpan={5} className="px-3 py-6 text-center text-text-muted">No projection data for week {week}+. Generate projections first.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const TABS = ['Dashboard', 'Leaderboards', 'Waiver Wire', 'Draft', 'Trade Analyzer', 'Power Rankings'] as const;
type Tab = typeof TABS[number];

export default function FantasyPage() {
  const [active, setActive] = useState<Tab>('Dashboard');
  const [rosterIds, setRosterIds] = useState<number[]>([]);

  return (
    <div className="animate-fade-up">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold text-text-primary tracking-tight">
          Fantasy Football
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Projections · Draft rankings · Trade analysis · Waiver wire · Power rankings
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-border mb-8 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActive(tab)}
            className={`relative px-4 py-3 font-display text-sm font-medium uppercase tracking-widest transition-colors whitespace-nowrap shrink-0 ${
              active === tab ? 'text-accent' : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {tab}
            {active === tab && (
              <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-accent rounded-full" />
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {active === 'Dashboard' && (
        <div className="space-y-6">
          <DashboardTab />
          <RosterImportHelper onImported={setRosterIds} />
          {rosterIds.length > 0 && (
            <p className="text-xs text-win">Roster set — {rosterIds.length} players imported.</p>
          )}
        </div>
      )}
      {active === 'Leaderboards'   && <LeaderboardsTab />}
      {active === 'Waiver Wire'    && <WaiverTab />}
      {active === 'Draft'          && <DraftTab />}
      {active === 'Trade Analyzer' && <TradeTabWithValues />}
      {active === 'Power Rankings' && <PowerRankingsTab />}
    </div>
  );
}

function TradeTabWithValues() {
  const [week, setWeek] = useState(1);
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <label className="text-xs text-text-muted font-display uppercase tracking-widest">Current Week</label>
        <select value={week} onChange={(e) => setWeek(Number(e.target.value))}
          className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent">
          {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => <option key={w} value={w}>Week {w}</option>)}
        </select>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6">
        <TradeTab externalWeek={week} />
        <TradeValueBoard week={week} season={2024} />
      </div>
    </div>
  );
}
