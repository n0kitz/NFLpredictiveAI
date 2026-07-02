import { useEffect, useMemo, useReducer, useState } from 'react';
import { api } from '../api/client';
import type { DraftRanking } from '../api/types';
import Spinner from '../components/Spinner';
import { UPCOMING_SEASON } from '../config';
import { type PositionFilter } from './fantasy/helpers';
import { useLeagueSettings, NFL_DEFAULT_SLOTS, type Scoring } from './fantasy/leagueSettings';
import {
  PositionFilterBar, ScoringToggle, PosBadge, Headshot,
} from './fantasy/shared';
import {
  applyNeedBoost, draftReducer, loadDraftState, myRoster, myTeamIdx,
  picksUntilMine, positionalNeeds, saveDraftState, teamForPick,
  tierBreakPositions, type DraftState,
} from './fantasy/draftBoard';

export default function DraftBoardPage() {
  const [state, dispatch] = useReducer(draftReducer, undefined, loadDraftState);
  const [rankings, setRankings] = useState<DraftRanking[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => saveDraftState(state), [state]);

  const { scoring, leagueSize } = state.settings;
  useEffect(() => {
    if (!state.started) return;
    setLoading(true);
    api.getDraftRankings(UPCOMING_SEASON, scoring, 'all', leagueSize)
      .then(setRankings)
      .catch(() => setRankings([]))
      .finally(() => setLoading(false));
  }, [state.started, scoring, leagueSize]);

  if (!state.started) {
    return <DraftSetup onStart={(settings) => dispatch({ type: 'SETUP', settings })} />;
  }
  return (
    <DraftRoom
      state={state}
      rankings={rankings}
      loading={loading}
      onPick={(playerId) => dispatch({ type: 'PICK', playerId })}
      onUndo={() => dispatch({ type: 'UNDO' })}
      onReset={() => {
        if (window.confirm('Reset the draft board? All tracked picks are lost.')) {
          dispatch({ type: 'RESET' });
        }
      }}
    />
  );
}

// ── Setup form ────────────────────────────────────────────────────────────────

function DraftSetup({ onStart }: {
  onStart: (s: DraftState['settings']) => void;
}) {
  const [leagueSettings] = useLeagueSettings();
  const [leagueSize, setLeagueSize] = useState(leagueSettings.leagueSize);
  const [mySlot, setMySlot] = useState(1);
  const [scoring, setScoring] = useState<Scoring>(leagueSettings.scoring);
  const rounds = Object.values(NFL_DEFAULT_SLOTS).reduce((a, b) => a + b, 0);

  return (
    <div className="max-w-lg mx-auto mt-12 rounded-xl border border-border bg-surface-850 p-8 space-y-6">
      <div>
        <h1 className="font-display font-extrabold text-xl text-text-primary tracking-tight">
          Live Draft Board
        </h1>
        <p className="text-xs text-text-muted mt-1">
          Track every pick of your fantasy.nfl.com snake draft and always see the
          best available player by value. Picks are saved locally — a refresh
          loses nothing.
        </p>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <label className="text-xs text-text-muted font-display uppercase tracking-widest">Teams</label>
          <select
            value={leagueSize}
            onChange={(e) => { setLeagueSize(Number(e.target.value)); setMySlot(1); }}
            className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
          >
            {Array.from({ length: 13 }, (_, i) => i + 8).map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center justify-between">
          <label className="text-xs text-text-muted font-display uppercase tracking-widest">My draft slot</label>
          <select
            value={mySlot}
            onChange={(e) => setMySlot(Number(e.target.value))}
            className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
          >
            {Array.from({ length: leagueSize }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center justify-between">
          <label className="text-xs text-text-muted font-display uppercase tracking-widest">Scoring</label>
          <ScoringToggle value={scoring} onChange={(s) => setScoring(s as Scoring)} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-muted font-display uppercase tracking-widest">Rounds</span>
          <span className="text-sm text-text-secondary tabular-nums">{rounds} (QB/2RB/2WR/TE/FLEX/K/DST + 7 bench)</span>
        </div>
      </div>

      <button
        onClick={() => onStart({
          leagueSize, mySlot, rounds, scoring,
          rosterSlots: { ...NFL_DEFAULT_SLOTS },
        })}
        className="w-full py-2.5 rounded bg-accent text-surface-900 font-display font-bold uppercase tracking-wide text-sm hover:opacity-90 transition-opacity"
      >
        Start Draft
      </button>
    </div>
  );
}

// ── Draft room ───────────────────────────────────────────────────────────────

function DraftRoom({ state, rankings, loading, onPick, onUndo, onReset }: {
  state: DraftState;
  rankings: DraftRanking[];
  loading: boolean;
  onPick: (playerId: number) => void;
  onUndo: () => void;
  onReset: () => void;
}) {
  const [search, setSearch] = useState('');
  const [position, setPosition] = useState<PositionFilter>('ALL');

  const pickedIds = useMemo(
    () => new Set(state.picks.map((p) => p.playerId)), [state.picks]);
  const available = useMemo(
    () => rankings.filter((r) => !pickedIds.has(r.player_id)),
    [rankings, pickedIds]);

  const rankingById = useMemo(() => {
    const m = new Map<number, DraftRanking>();
    for (const r of rankings) m.set(r.player_id, r);
    return m;
  }, [rankings]);

  const myIds = myRoster(state);
  const myPositions = myIds
    .map((id) => rankingById.get(id)?.position)
    .filter((p): p is string => Boolean(p));
  const needs = positionalNeeds(myPositions, state.settings.rosterSlots);
  const suggestions = useMemo(
    () => applyNeedBoost(available, needs),
    [available, needs]);
  const tierBreaks = tierBreakPositions(available);

  const nextOverall = state.picks.length + 1;
  const totalPicks = state.settings.leagueSize * state.settings.rounds;
  const round = Math.min(state.settings.rounds,
    Math.floor((nextOverall - 1) / state.settings.leagueSize) + 1);
  const onClockIdx = nextOverall <= totalPicks
    ? teamForPick(nextOverall, state.settings.leagueSize) : -1;
  const untilMine = picksUntilMine(state);
  const draftOver = nextOverall > totalPicks;

  const visible = suggestions.filter((r) => {
    if (position !== 'ALL' && r.position !== position) return false;
    if (search) return r.full_name.toLowerCase().includes(search.toLowerCase());
    return true;
  }).slice(0, 60);

  return (
    <div className="space-y-4">
      {/* Clock bar */}
      <div className="flex items-center gap-4 flex-wrap rounded-xl border border-border bg-surface-850 px-5 py-3">
        <div className="font-display text-sm">
          {draftOver ? (
            <span className="text-accent font-bold uppercase">Draft complete</span>
          ) : (
            <>
              <span className="text-text-muted uppercase text-[10px] tracking-widest mr-2">
                Round {round} · Pick {nextOverall}
              </span>
              {untilMine === 0 ? (
                <span className="text-accent font-bold uppercase animate-pulse">You're on the clock!</span>
              ) : (
                <span className="text-text-secondary">
                  Team {onClockIdx + 1} picks — you in <b className="text-text-primary">{untilMine}</b>
                </span>
              )}
            </>
          )}
        </div>
        <div className="ml-auto flex gap-2">
          <button
            onClick={onUndo}
            disabled={state.picks.length === 0}
            className="px-3 py-1.5 rounded border border-border text-xs font-display uppercase tracking-wide text-text-muted hover:text-text-secondary disabled:opacity-30"
          >
            Undo
          </button>
          <button
            onClick={onReset}
            className="px-3 py-1.5 rounded border border-border text-xs font-display uppercase tracking-wide text-text-muted hover:text-red-400"
          >
            Reset
          </button>
        </div>
      </div>

      {tierBreaks.length > 0 && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-xs text-amber-300">
          ⚠ Tier break imminent: {tierBreaks.join(', ')} — two or fewer players left
          in the top remaining tier.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Best available */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <PositionFilterBar value={position} onChange={setPosition} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search player…"
              className="bg-surface-800 border border-border rounded px-3 py-1.5 text-sm text-text-secondary placeholder:text-text-muted focus:outline-none focus:border-accent w-44"
            />
          </div>
          {loading ? <Spinner text="Loading rankings…" /> : (
            <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {['Player', 'Pos', 'Tier', 'ADP', 'Proj', 'Value', ''].map((h) => (
                      <th key={h} className="px-3 py-2.5 text-left text-[10px] font-display uppercase tracking-widest text-text-muted">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visible.map((r) => {
                    const needed = (r.position && needs[r.position] > 0)
                      || (r.position && ['RB', 'WR', 'TE'].includes(r.position) && needs.FLEX > 0);
                    return (
                      <tr key={r.player_id} className="border-b border-border/50 hover:bg-surface-800 transition-colors">
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-2">
                            <Headshot url={r.headshot_url} name={r.full_name} />
                            <span className="text-text-primary font-medium text-xs truncate max-w-[150px]">{r.full_name}</span>
                            {needed && <span title="Fills a starting slot you still need" className="text-[9px] text-accent">●</span>}
                          </div>
                        </td>
                        <td className="px-3 py-2"><PosBadge pos={r.position} /></td>
                        <td className="px-3 py-2 text-[10px] text-text-muted">T{r.tier}</td>
                        <td className="px-3 py-2 tabular-nums text-xs text-text-muted">{r.adp.toFixed(1)}</td>
                        <td className="px-3 py-2 tabular-nums text-xs text-text-secondary">{r.projected_season_points.toFixed(0)}</td>
                        <td className="px-3 py-2 tabular-nums text-xs font-bold" style={{ color: 'var(--color-accent)' }}>
                          {r.needScore.toFixed(0)}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex gap-1">
                            <button
                              onClick={() => onPick(r.player_id)}
                              disabled={draftOver}
                              title={untilMine === 0 ? 'Draft to MY team' : 'Mark as drafted by the team on the clock'}
                              className={`px-2.5 py-1 rounded text-[10px] font-display font-bold uppercase transition-colors disabled:opacity-30 ${
                                untilMine === 0
                                  ? 'bg-accent text-surface-900'
                                  : 'border border-border text-text-muted hover:text-text-secondary'
                              }`}
                            >
                              {untilMine === 0 ? 'Draft' : 'Taken'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {visible.length === 0 && !loading && (
                    <tr><td colSpan={7} className="px-4 py-10 text-center text-text-muted text-xs">No players match.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Sidebar: my roster + needs + recent picks */}
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-surface-850 p-4">
            <h3 className="font-display font-bold text-xs uppercase tracking-widest text-text-muted mb-3">
              My Roster ({myIds.length}/{state.settings.rounds})
            </h3>
            <div className="space-y-1.5">
              {myIds.length === 0 && (
                <p className="text-xs text-text-muted">No picks yet — slot {state.settings.mySlot} of {state.settings.leagueSize}.</p>
              )}
              {myIds.map((id) => {
                const r = rankingById.get(id);
                return (
                  <div key={id} className="flex items-center gap-2 text-xs">
                    <PosBadge pos={r?.position ?? null} />
                    <span className="text-text-secondary truncate">{r?.full_name ?? `#${id}`}</span>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 pt-3 border-t border-border/50">
              <h4 className="text-[10px] font-display uppercase tracking-widest text-text-muted mb-2">Still need</h4>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(needs).filter(([, n]) => n > 0).map(([slot, n]) => (
                  <span key={slot} className="px-2 py-0.5 rounded bg-surface-800 border border-border text-[10px] text-text-secondary">
                    {slot}{n > 1 ? ` ×${n}` : ''}
                  </span>
                ))}
                {Object.values(needs).every((n) => n === 0) && (
                  <span className="text-[10px] text-accent">All starters filled ✓</span>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-surface-850 p-4">
            <h3 className="font-display font-bold text-xs uppercase tracking-widest text-text-muted mb-3">Recent Picks</h3>
            <div className="space-y-1.5 max-h-72 overflow-y-auto">
              {[...state.picks].reverse().slice(0, 20).map((p) => {
                const r = rankingById.get(p.playerId);
                const mine = p.teamIdx === myTeamIdx(state);
                return (
                  <div key={p.overall} className="flex items-center gap-2 text-xs">
                    <span className="text-text-muted tabular-nums w-8">{p.overall}.</span>
                    <span className={`w-10 text-[10px] ${mine ? 'text-accent font-bold' : 'text-text-muted'}`}>
                      {mine ? 'ME' : `T${p.teamIdx + 1}`}
                    </span>
                    <span className="text-text-secondary truncate">{r?.full_name ?? `#${p.playerId}`}</span>
                  </div>
                );
              })}
              {state.picks.length === 0 && (
                <p className="text-xs text-text-muted">Draft hasn't started.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
