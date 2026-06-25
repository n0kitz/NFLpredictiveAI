import { useState, useEffect, useRef } from 'react';
import { api } from '../../api/client';
import type {
  TradeAnalysis, TradePlayer, PlayerSearchResult, TradeValue,
} from '../../api/types';
import Spinner from '../../components/Spinner';
import { CURRENT_SEASON, LAST_COMPLETED_SEASON } from '../../config';
import { PosBadge, Headshot } from './shared';

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
  const [season] = useState(CURRENT_SEASON);
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

export default function TradeTabWithValues() {
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
        <TradeValueBoard week={week} season={LAST_COMPLETED_SEASON} />
      </div>
    </div>
  );
}
