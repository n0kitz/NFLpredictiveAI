import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { DraftRanking } from '../api/types';
import Spinner from '../components/Spinner';
import { UPCOMING_SEASON } from '../config';
import { useLeagueSettings, NFL_DEFAULT_SLOTS, type Scoring } from './fantasy/leagueSettings';
import { PosBadge, Headshot } from './fantasy/shared';
import { teamForPick } from './fantasy/draftBoard';
import {
  STRATEGIES, strategyIds, BOT_ARCHETYPES, assignBotArchetypes, botPick,
  adpLooksSynthetic, evaluateRoster, makeRng, runBatch,
  type BatchRow, type SimSettings,
} from './fantasy/draftSim';

type Mode = 'batch' | 'interactive';

export default function DraftSimulatorPage() {
  const [league] = useLeagueSettings();
  const [rankings, setRankings] = useState<DraftRanking[]>([]);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<Mode>('batch');

  const [leagueSize, setLeagueSize] = useState(league.leagueSize);
  const [mySlot, setMySlot] = useState(1);
  const [rounds, setRounds] = useState(15);
  const [scoring, setScoring] = useState<Scoring>(league.scoring);

  const settings: SimSettings = useMemo(
    () => ({ leagueSize, mySlot, rounds, scoring, rosterSlots: NFL_DEFAULT_SLOTS }),
    [leagueSize, mySlot, rounds, scoring],
  );

  useEffect(() => {
    setLoading(true);
    api.getDraftRankings(UPCOMING_SEASON, scoring, 'all', leagueSize)
      .then(setRankings)
      .catch(() => setRankings([]))
      .finally(() => setLoading(false));
  }, [scoring, leagueSize]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Draft Simulator</h1>
          <p className="text-sm text-text-muted">
            Run mock drafts against bot opponents to see which strategy actually wins
            from your slot — then rehearse it pick by pick.
          </p>
        </div>
        <Link
          to="/draft"
          className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:border-border-strong hover:text-text-primary"
        >
          → Live draft board
        </Link>
      </header>

      <SimSettingsBar
        leagueSize={leagueSize}
        setLeagueSize={(n) => {
          setLeagueSize(n);
          // A smaller league can't contain a high slot.
          if (mySlot > n) setMySlot(n);
        }}
        mySlot={mySlot} setMySlot={setMySlot}
        rounds={rounds} setRounds={setRounds}
        scoring={scoring} setScoring={setScoring}
      />

      <div className="flex gap-2 border-b border-border">
        {(['batch', 'interactive'] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              mode === m
                ? 'border-b-2 border-accent text-text-primary'
                : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {m === 'batch' ? 'Compare strategies' : 'Mock draft'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Spinner /></div>
      ) : rankings.length === 0 ? (
        <EmptyState />
      ) : mode === 'batch' ? (
        <BatchMode players={rankings} settings={settings} />
      ) : (
        <InteractiveMode players={rankings} settings={settings} />
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-border bg-surface-800 p-8 text-center">
      <p className="text-text-secondary">No draft rankings available.</p>
      <p className="mt-1 text-sm text-text-muted">
        Rankings need roster entries for {UPCOMING_SEASON}. Run{' '}
        <code className="rounded bg-surface-700 px-1.5 py-0.5 text-xs">
          scripts/import_rosters.py --season {UPCOMING_SEASON} --skip-stats
        </code>
      </p>
    </div>
  );
}

// ── Settings ─────────────────────────────────────────────────────────────────

function SimSettingsBar(props: {
  leagueSize: number; setLeagueSize: (n: number) => void;
  mySlot: number; setMySlot: (n: number) => void;
  rounds: number; setRounds: (n: number) => void;
  scoring: Scoring; setScoring: (s: Scoring) => void;
}) {
  const { leagueSize, setLeagueSize, mySlot, setMySlot, rounds, setRounds, scoring, setScoring } = props;
  const field = 'rounded-lg border border-border bg-surface-700 px-3 py-1.5 text-sm text-text-primary';

  return (
    <div className="flex flex-wrap items-end gap-4 rounded-xl border border-border bg-surface-800 p-4">
      <label className="flex flex-col gap-1">
        <span className="text-xs uppercase tracking-wide text-text-muted">Teams</span>
        <select className={field} value={leagueSize} onChange={(e) => setLeagueSize(+e.target.value)}>
          {Array.from({ length: 13 }, (_, i) => i + 8).map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs uppercase tracking-wide text-text-muted">My slot</span>
        <select className={field} value={mySlot} onChange={(e) => setMySlot(+e.target.value)}>
          {Array.from({ length: leagueSize }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs uppercase tracking-wide text-text-muted">Rounds</span>
        <select className={field} value={rounds} onChange={(e) => setRounds(+e.target.value)}>
          {[13, 14, 15, 16, 17].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs uppercase tracking-wide text-text-muted">Scoring</span>
        <select className={field} value={scoring} onChange={(e) => setScoring(e.target.value as Scoring)}>
          <option value="standard">Standard</option>
          <option value="half_ppr">Half PPR</option>
          <option value="ppr">PPR</option>
        </select>
      </label>
    </div>
  );
}

// ── Batch mode ───────────────────────────────────────────────────────────────

const SIM_COUNTS = [25, 50, 100, 200];

function BatchMode({ players, settings }: { players: DraftRanking[]; settings: SimSettings }) {
  const all = strategyIds();
  const [selected, setSelected] = useState<string[]>(all);
  const [sims, setSims] = useState(50);
  const [run_, setRun] = useState<{ rows: BatchRow[]; key: string } | null>(null);
  const [running, setRunning] = useState(false);

  // Results belong to the exact config that produced them; anything else is stale.
  const configKey = JSON.stringify([settings, [...selected].sort(), sims]);
  const rows = run_ && run_.key === configKey ? run_.rows : null;

  function toggle(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  }

  function run() {
    if (selected.length < 2) return;
    setRunning(true);
    // Yield a frame so the button can show its running state before we block.
    setTimeout(() => {
      setRun({ rows: runBatch(players, settings, selected, sims, 1), key: configKey });
      setRunning(false);
    }, 16);
  }

  const spread = rows && rows.length > 1 ? rows[0].avgPoints - rows[rows.length - 1].avgPoints : 0;
  const syntheticAdp = adpLooksSynthetic(players);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-surface-800 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold text-text-primary">Strategies to compare</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-text-muted">Drafts each</span>
            <select
              className="rounded-lg border border-border bg-surface-700 px-2 py-1 text-sm text-text-primary"
              value={sims}
              onChange={(e) => setSims(+e.target.value)}
            >
              {SIM_COUNTS.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            <button
              onClick={run}
              disabled={running || selected.length < 2}
              className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-surface-900 transition-colors hover:bg-accent-hover disabled:opacity-40"
            >
              {running ? 'Running…' : 'Run simulation'}
            </button>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {all.map((id) => (
            <label
              key={id}
              title={STRATEGIES[id].description}
              className={`flex cursor-pointer items-start gap-2 rounded-lg border p-2 text-sm transition-colors ${
                selected.includes(id)
                  ? 'border-accent/50 bg-accent/10 text-text-primary'
                  : 'border-border text-text-muted hover:border-border-strong'
              }`}
            >
              <input
                type="checkbox"
                checked={selected.includes(id)}
                onChange={() => toggle(id)}
                className="mt-0.5 accent-[var(--color-accent)]"
              />
              <span>{STRATEGIES[id].label}</span>
            </label>
          ))}
        </div>
        {selected.length < 2 && (
          <p className="mt-2 text-xs text-loss">Pick at least two strategies to compare.</p>
        )}
        {syntheticAdp && selected.includes('value-adp') && (
          <p className="mt-2 text-xs text-conf-medium">
            ADP is synthesised from the rankings themselves — no real market data is loaded, so
            “Value vs ADP” has nothing to exploit and its result here is meaningless. Import a
            FantasyPros CSV with{' '}
            <code className="rounded bg-surface-700 px-1 py-0.5">scripts/import_adp.py</code> to
            make it real.
          </p>
        )}
      </div>

      {rows && (
        <div className="rounded-xl border border-border bg-surface-800 p-4">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-semibold text-text-primary">
              Results — {sims} drafts each, slot {settings.mySlot} of {settings.leagueSize}
            </h2>
            <span className="text-xs text-text-muted">
              Best legal starting lineup, projected season points
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
                  <th className="py-2 pr-3">#</th>
                  <th className="py-2 pr-3">Strategy</th>
                  <th className="py-2 pr-3 text-right">Avg pts</th>
                  <th className="py-2 pr-3 text-right">Win %</th>
                  <th className="py-2 pr-3 text-right">Best</th>
                  <th className="py-2 pr-3 text-right">Worst</th>
                  <th className="py-2 text-right">Range</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.strategy} className="border-b border-border/50 last:border-0">
                    <td className="py-2 pr-3 text-text-muted">{i + 1}</td>
                    <td className="py-2 pr-3">
                      <span className={i === 0 ? 'font-semibold text-win' : 'text-text-primary'}>
                        {r.label}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right font-mono text-text-primary">
                      {r.avgPoints.toFixed(1)}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono text-text-secondary">
                      {r.winPct.toFixed(1)}%
                    </td>
                    <td className="py-2 pr-3 text-right font-mono text-text-muted">{r.best.toFixed(0)}</td>
                    <td className="py-2 pr-3 text-right font-mono text-text-muted">{r.worst.toFixed(0)}</td>
                    <td className="py-2 text-right font-mono text-text-muted">
                      {(r.best - r.worst).toFixed(0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-3 text-sm text-text-secondary">
            <span className="font-semibold text-win">{rows[0].label}</span> wins from slot{' '}
            {settings.mySlot} — {spread.toFixed(1)} points ahead of the worst option.
            {spread < 15 && (
              <span className="text-text-muted">
                {' '}That gap is small; from this slot the strategy matters less than who falls to you.
              </span>
            )}
          </p>
        </div>
      )}

      {!rows && !running && (
        <p className="text-sm text-text-muted">
          Every strategy faces the same seeded set of opponents, so differences come from the
          strategy rather than luck of the draw.
        </p>
      )}
    </div>
  );
}

// ── Interactive mock draft ───────────────────────────────────────────────────

interface MockState {
  taken: Set<number>;
  myPicks: DraftRanking[];
  board: Array<{ overall: number; teamIdx: number; player: DraftRanking }>;
  overall: number;
}

function InteractiveMode({ players, settings }: { players: DraftRanking[]; settings: SimSettings }) {
  const [seed, setSeed] = useState(1);
  const [strategy, setStrategy] = useState('need-based');
  const [state, setState] = useState<MockState>(() => ({
    taken: new Set(), myPicks: [], board: [], overall: 1,
  }));
  const [history, setHistory] = useState<MockState[]>([]);

  const myIdx = settings.mySlot - 1;
  const totalPicks = settings.leagueSize * settings.rounds;
  const bots = useMemo(() => assignBotArchetypes(settings, makeRng(seed)), [settings, seed]);
  const rng = useMemo(() => makeRng(seed + 7), [seed]);

  const available = useMemo(
    () => players.filter((p) => !state.taken.has(p.player_id)),
    [players, state.taken],
  );

  const round = Math.floor((state.overall - 1) / settings.leagueSize) + 1;
  const onClock = teamForPick(state.overall, settings.leagueSize);
  const myTurn = onClock === myIdx;
  const done = state.overall > totalPicks;

  function reset() {
    setState({ taken: new Set(), myPicks: [], board: [], overall: 1 });
    setHistory([]);
  }

  function commit(next: MockState) {
    setHistory((h) => [...h, state]);
    setState(next);
  }

  /** Advance the draft until it's my turn again (or the draft ends). */
  function runBotsFrom(start: MockState): MockState {
    const taken = new Set(start.taken);
    const board = [...start.board];
    let overall = start.overall;

    while (overall <= totalPicks) {
      const teamIdx = teamForPick(overall, settings.leagueSize);
      if (teamIdx === myIdx) break;

      const pool = players.filter((p) => !taken.has(p.player_id));
      if (!pool.length) break;

      const botRoster = board.filter((b) => b.teamIdx === teamIdx).map((b) => b.player);
      const r = Math.floor((overall - 1) / settings.leagueSize) + 1;
      // Reuse the engine by simulating a single pick for this bot.
      const choice = botPick(bots[teamIdx], pool, botRoster, r, settings, rng);
      taken.add(choice.player_id);
      board.push({ overall, teamIdx, player: choice });
      overall++;
    }
    return { taken, board, overall, myPicks: start.myPicks };
  }

  function draftPlayer(p: DraftRanking) {
    const taken = new Set(state.taken);
    taken.add(p.player_id);
    const afterMe: MockState = {
      taken,
      myPicks: [...state.myPicks, p],
      board: [...state.board, { overall: state.overall, teamIdx: myIdx, player: p }],
      overall: state.overall + 1,
    };
    commit(runBotsFrom(afterMe));
  }

  function autoPick() {
    const choice = STRATEGIES[strategy].pick({
      available, myPicks: state.myPicks, round, settings, rng,
    });
    const p = available.find((x) => x.player_id === choice);
    if (p) draftPlayer(p);
  }

  function undo() {
    const prev = history[history.length - 1];
    if (!prev) return;
    setHistory((h) => h.slice(0, -1));
    setState(prev);
  }

  // Bots pick before my very first turn when I'm not at slot 1.
  useEffect(() => {
    if (state.overall === 1 && !state.board.length && myIdx !== 0) {
      setState((s) => runBotsFrom(s));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.overall, state.board.length, myIdx, seed, settings]);

  const evaluation = evaluateRoster(state.myPicks, settings);
  const suggestions = useMemo(() => {
    if (!available.length) return [];
    const ids = new Set<number>();
    const out: DraftRanking[] = [];
    for (const id of strategyIds()) {
      const choice = STRATEGIES[id].pick({
        available, myPicks: state.myPicks, round, settings, rng: makeRng(seed),
      });
      if (!ids.has(choice)) {
        ids.add(choice);
        const p = available.find((x) => x.player_id === choice);
        if (p) out.push(p);
      }
    }
    return out.slice(0, 4);
  }, [available, state.myPicks, round, settings, seed]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface-800 p-4">
        <div className="text-sm">
          {done ? (
            <span className="font-semibold text-win">Draft complete</span>
          ) : myTurn ? (
            <span className="font-semibold text-accent">
              Round {round} · Pick {state.overall} — you're on the clock
            </span>
          ) : (
            <span className="text-text-muted">Round {round} · Pick {state.overall}</span>
          )}
          <span className="ml-2 text-text-muted">
            · {evaluation.starterPoints.toFixed(1)} projected starter pts
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="rounded-lg border border-border bg-surface-700 px-2 py-1 text-sm text-text-primary"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            title="Strategy used by the auto-pick button"
          >
            {strategyIds().map((id) => (
              <option key={id} value={id}>{STRATEGIES[id].label}</option>
            ))}
          </select>
          <button
            onClick={autoPick}
            disabled={!myTurn || done}
            className="rounded-lg border border-border px-3 py-1 text-sm text-text-secondary hover:border-border-strong hover:text-text-primary disabled:opacity-40"
          >
            Auto-pick
          </button>
          <button
            onClick={undo}
            disabled={!history.length}
            className="rounded-lg border border-border px-3 py-1 text-sm text-text-secondary hover:border-border-strong hover:text-text-primary disabled:opacity-40"
          >
            Undo
          </button>
          <button
            onClick={() => { setSeed((s) => s + 1); reset(); }}
            className="rounded-lg border border-border px-3 py-1 text-sm text-text-secondary hover:border-border-strong hover:text-text-primary"
          >
            New draft
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="rounded-xl border border-border bg-surface-800 p-4">
          <h2 className="mb-3 font-semibold text-text-primary">
            {myTurn && !done ? 'Best available' : 'Available players'}
          </h2>

          {suggestions.length > 0 && myTurn && !done && (
            <div className="mb-3 rounded-lg border border-accent/30 bg-accent/5 p-2">
              <p className="mb-1.5 text-xs uppercase tracking-wide text-text-muted">
                What each strategy would take
              </p>
              <div className="flex flex-wrap gap-1.5">
                {suggestions.map((p) => (
                  <button
                    key={p.player_id}
                    onClick={() => draftPlayer(p)}
                    className="flex items-center gap-1.5 rounded-lg border border-border bg-surface-700 px-2 py-1 text-xs hover:border-accent"
                  >
                    <PosBadge pos={p.position} />
                    <span className="text-text-primary">{p.full_name}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="max-h-[28rem] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface-800">
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
                  <th className="py-2 pr-2">Player</th>
                  <th className="py-2 pr-2">Pos</th>
                  <th className="py-2 pr-2 text-right">VBD</th>
                  <th className="py-2 pr-2 text-right">Proj</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {available.slice(0, 60).map((p) => (
                  <tr key={p.player_id} className="border-b border-border/40 last:border-0">
                    <td className="py-1.5 pr-2">
                      <div className="flex items-center gap-2">
                        <Headshot url={p.headshot_url} name={p.full_name} />
                        <span className="text-text-primary">{p.full_name}</span>
                        <span className="text-xs text-text-muted">{p.team_abbr}</span>
                      </div>
                    </td>
                    <td className="py-1.5 pr-2"><PosBadge pos={p.position} /></td>
                    <td className="py-1.5 pr-2 text-right font-mono text-text-secondary">
                      {(p.vbd ?? 0).toFixed(0)}
                    </td>
                    <td className="py-1.5 pr-2 text-right font-mono text-text-muted">
                      {p.projected_season_points.toFixed(0)}
                    </td>
                    <td className="py-1.5 text-right">
                      <button
                        onClick={() => draftPlayer(p)}
                        disabled={!myTurn || done}
                        className="rounded border border-border px-2 py-0.5 text-xs text-text-secondary hover:border-accent hover:text-text-primary disabled:opacity-30"
                      >
                        Draft
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-surface-800 p-4">
            <h2 className="mb-2 font-semibold text-text-primary">
              My roster ({state.myPicks.length}/{settings.rounds})
            </h2>
            {state.myPicks.length === 0 ? (
              <p className="text-sm text-text-muted">No picks yet.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {state.myPicks.map((p, i) => (
                  <li key={p.player_id} className="flex items-center gap-2">
                    <span className="w-8 font-mono text-xs text-text-muted">{i + 1}.</span>
                    <PosBadge pos={p.position} />
                    <span className="text-text-primary">{p.full_name}</span>
                  </li>
                ))}
              </ul>
            )}
            {evaluation.missing.length > 0 && (
              <p className="mt-2 text-xs text-loss">
                Unfilled: {evaluation.missing.join(', ')}
              </p>
            )}
          </div>

          <div className="rounded-xl border border-border bg-surface-800 p-4">
            <h2 className="mb-2 font-semibold text-text-primary">Opponents</h2>
            <ul className="space-y-1 text-xs text-text-muted">
              {Object.entries(bots).map(([idx, archetype]) => (
                <li key={idx} className="flex justify-between">
                  <span>Team {Number(idx) + 1}</span>
                  <span className="text-text-secondary">{BOT_ARCHETYPES[archetype].label}</span>
                </li>
              ))}
            </ul>
          </div>

          {state.board.length > 0 && (
            <div className="rounded-xl border border-border bg-surface-800 p-4">
              <h2 className="mb-2 font-semibold text-text-primary">Recent picks</h2>
              <ul className="space-y-1 text-xs">
                {state.board.slice(-8).reverse().map((b) => (
                  <li key={b.overall} className="flex items-center gap-2">
                    <span className="w-8 font-mono text-text-muted">{b.overall}.</span>
                    <PosBadge pos={b.player.position} />
                    <span className={b.teamIdx === myIdx ? 'text-accent' : 'text-text-secondary'}>
                      {b.player.full_name}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
