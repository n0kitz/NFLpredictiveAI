import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { DraftRanking } from '../../api/types';
import Spinner from '../../components/Spinner';
import BoomBustBadge from '../../components/BoomBustBadge';
import { CURRENT_SEASON, recentSeasons } from '../../config';
import { type PositionFilter } from './helpers';
import {
  PositionFilterBar, ScoringToggle, PosBadge, Headshot,
} from './shared';

export default function DraftTab() {
  const [season, setSeason] = useState(CURRENT_SEASON);
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
            {recentSeasons(3).map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <ScoringToggle value={scoring} onChange={setScoring} />
        <PositionFilterBar value={position} onChange={setPosition} />
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
                {[
                  { k: 'Rank' },
                  { k: 'Tier' },
                  { k: 'Player' },
                  { k: 'Pos' },
                  { k: 'Team' },
                  { k: 'ADP' },
                  { k: 'Pos Rank' },
                  { k: 'Proj Pts' },
                  { k: 'VBD', t: 'Value Based Drafting: projected season points above replacement-level at this position (12-team league baseline)' },
                ].map(({ k, t }) => (
                  <th
                    key={k}
                    title={t}
                    className={`px-4 py-3 text-left text-[10px] font-display uppercase tracking-widest text-text-muted ${t ? 'cursor-help' : ''}`}
                  >
                    {k}
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
                      <td colSpan={9} className="px-4 py-2 bg-surface-900 border-b border-border">
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
                        <div className="flex flex-col min-w-0">
                          <span className="text-text-primary font-medium text-xs truncate max-w-[140px]">{r.full_name}</span>
                          <BoomBustBadge boomPct={r.boom_pct} bustPct={r.bust_pct} />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2.5"><PosBadge pos={r.position} /></td>
                    <td className="px-4 py-2.5 text-text-muted text-xs">{r.team_abbr ?? '—'}</td>
                    <td className="px-4 py-2.5 text-text-secondary tabular-nums text-xs">{r.adp.toFixed(1)}</td>
                    <td className="px-4 py-2.5 text-text-muted tabular-nums text-xs">{r.position} {r.position_rank}</td>
                    <td className="px-4 py-2.5 font-bold tabular-nums text-text-primary">
                      {r.projected_season_points.toFixed(0)}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums text-xs" style={{ color: r.vbd && r.vbd > 0 ? 'var(--color-accent)' : 'var(--color-text-muted)' }}>
                      {r.vbd != null ? r.vbd.toFixed(0) : '—'}
                    </td>
                  </tr>,
                ];
              })}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-text-muted text-xs">
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
