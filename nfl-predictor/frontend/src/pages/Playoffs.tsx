import { useState, useCallback } from 'react';
import { useTeams } from '../hooks/useApi';
import TeamSelector from '../components/TeamSelector';
import { api } from '../api/client';
import { getTeamColors } from '../theme/teamColors';

interface MatchupResult {
  home: string;
  away: string;
  homeProb: number;
  awayProb: number;
  winner: string;
}

interface BracketState {
  afc: {
    seeds: string[];
    wildCard: MatchupResult[];
    divisional: MatchupResult[];
    conference: MatchupResult | null;
    champion: string | null;
  };
  nfc: {
    seeds: string[];
    wildCard: MatchupResult[];
    divisional: MatchupResult[];
    conference: MatchupResult | null;
    champion: string | null;
  };
  superBowl: MatchupResult | null;
}

const EMPTY_BRACKET: BracketState = {
  afc: { seeds: Array(7).fill(''), wildCard: [], divisional: [], conference: null, champion: null },
  nfc: { seeds: Array(7).fill(''), wildCard: [], divisional: [], conference: null, champion: null },
  superBowl: null,
};

export default function Playoffs() {
  const { data: teamList } = useTeams();
  const [bracket, setBracket] = useState<BracketState>(EMPTY_BRACKET);
  const [loading, setLoading] = useState(false);
  const [simulated, setSimulated] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  const teams = teamList?.teams ?? [];
  const afcTeams = teams.filter((t) => t.conference === 'AFC');
  const nfcTeams = teams.filter((t) => t.conference === 'NFC');

  const setSeed = (conf: 'afc' | 'nfc', idx: number, abbr: string) => {
    setBracket((prev) => {
      const seeds = [...prev[conf].seeds];
      seeds[idx] = abbr;
      return { ...prev, [conf]: { ...prev[conf], seeds } };
    });
    setSimulated(false);
  };

  const allSeeded = bracket.afc.seeds.every(Boolean) && bracket.nfc.seeds.every(Boolean);
  const noDuplicates = new Set([...bracket.afc.seeds, ...bracket.nfc.seeds].filter(Boolean)).size ===
    [...bracket.afc.seeds, ...bracket.nfc.seeds].filter(Boolean).length;

  const simulate = useCallback(async () => {
    if (!allSeeded) return;
    setLoading(true);
    setSimError(null);

    async function predictMatch(home: string, away: string): Promise<MatchupResult> {
      const p = await api.predictGet(away, home);
      return {
        home, away,
        homeProb: p.home_win_probability,
        awayProb: p.away_win_probability,
        winner: p.home_win_probability > p.away_win_probability ? home : away,
      };
    }

    try {
      const result: BracketState = { ...EMPTY_BRACKET, afc: { ...bracket.afc, wildCard: [], divisional: [], conference: null, champion: null }, nfc: { ...bracket.nfc, wildCard: [], divisional: [], conference: null, champion: null }, superBowl: null };

      for (const conf of ['afc', 'nfc'] as const) {
        const s = result[conf].seeds;

        // Wild Card: #2 vs #7, #3 vs #6, #4 vs #5 (higher seed is home)
        const wc1 = await predictMatch(s[1], s[6]);
        const wc2 = await predictMatch(s[2], s[5]);
        const wc3 = await predictMatch(s[3], s[4]);
        result[conf].wildCard = [wc1, wc2, wc3];

        // Divisional: #1 vs lowest remaining seed, next two winners
        const wcWinners = [wc1.winner, wc2.winner, wc3.winner];
        // Re-seed: #1 faces lowest remaining seed
        const seedOrder = wcWinners.map((w) => ({ abbr: w, seed: s.indexOf(w) })).sort((a, b) => b.seed - a.seed);
        const div1 = await predictMatch(s[0], seedOrder[0].abbr); // #1 vs lowest
        const remaining = seedOrder.slice(1).sort((a, b) => a.seed - b.seed);
        const div2 = await predictMatch(remaining[0].abbr, remaining[1].abbr);
        result[conf].divisional = [div1, div2];

        // Conference championship
        const confGame = await predictMatch(div1.winner, div2.winner);
        result[conf].conference = confGame;
        result[conf].champion = confGame.winner;
      }

      // Super Bowl (NFC is home in odd years for simplicity)
      const sb = await predictMatch(result.nfc.champion!, result.afc.champion!);
      result.superBowl = sb;

      setBracket(result);
      setSimulated(true);
    } catch (err: unknown) {
      setSimError(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      setLoading(false);
    }
  }, [bracket.afc.seeds, bracket.nfc.seeds, allSeeded]);

  return (
    <div>
      {/* Header */}
      <div className="mb-8 animate-fade-up">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-px w-6 bg-accent" />
          <span className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold">
            Bracket Simulator
          </span>
        </div>
        <h1 className="font-display text-3xl font-bold text-text-primary uppercase tracking-tight">
          Playoffs
        </h1>
        <p className="text-text-secondary text-sm mt-2">
          Seed 14 teams, then simulate the entire playoff bracket.
        </p>
      </div>

      {simError && <p className="text-red-400 mb-4">{simError}</p>}

      {/* Seeding */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 animate-fade-up stagger-1">
        <SeedingPanel
          title="AFC Seeds"
          seeds={bracket.afc.seeds}
          teams={afcTeams}
          onSeed={(idx, abbr) => setSeed('afc', idx, abbr)}
        />
        <SeedingPanel
          title="NFC Seeds"
          seeds={bracket.nfc.seeds}
          teams={nfcTeams}
          onSeed={(idx, abbr) => setSeed('nfc', idx, abbr)}
        />
      </div>

      {/* Simulate button */}
      <button
        onClick={simulate}
        disabled={!allSeeded || !noDuplicates || loading}
        className="w-full mb-8 px-6 py-3.5 rounded-md bg-accent text-surface-900 font-display font-semibold text-sm uppercase tracking-wider
                   hover:bg-accent-hover disabled:opacity-25 disabled:cursor-not-allowed transition-all active:scale-[0.98]"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            Simulating...
          </span>
        ) : (
          'Simulate Bracket'
        )}
      </button>

      {/* Bracket results */}
      {simulated && (
        <div className="space-y-8 animate-fade-up">
          {/* Super Bowl champion */}
          {bracket.superBowl && (
            <div className="rounded-xl border-2 border-accent bg-surface-850 p-6 text-center">
              <p className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold mb-3">
                Predicted Champion
              </p>
              <div className="flex items-center justify-center gap-4">
                <div
                  className="w-16 h-16 rounded-lg flex items-center justify-center shadow-lg"
                  style={{ backgroundColor: getTeamColors(bracket.superBowl.winner).primary }}
                >
                  <span className="font-display font-bold text-white text-xl">{bracket.superBowl.winner}</span>
                </div>
              </div>
              <p className="text-text-secondary text-sm mt-3">
                {bracket.superBowl.away} {(bracket.superBowl.awayProb * 100).toFixed(0)}% &middot;{' '}
                {bracket.superBowl.home} {(bracket.superBowl.homeProb * 100).toFixed(0)}%
              </p>
            </div>
          )}

          {/* Conference brackets */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <ConferenceBracket title="AFC" data={bracket.afc} />
            <ConferenceBracket title="NFC" data={bracket.nfc} />
          </div>

          {/* Super Bowl */}
          {bracket.superBowl && (
            <RoundCard title="Super Bowl" matchups={[bracket.superBowl]} />
          )}
        </div>
      )}
    </div>
  );
}

function SeedingPanel({
  title, seeds, teams, onSeed,
}: {
  title: string;
  seeds: string[];
  teams: { team_id: number; abbreviation: string; name: string; city: string; conference: string; division: string; franchise_id: string | null; active_from: number | null; active_until: number | null }[];
  onSeed: (idx: number, abbr: string) => void;
}) {
  const usedAbbrs = seeds.filter(Boolean);
  return (
    <div className="rounded-lg border border-border bg-surface-850 p-5">
      <h3 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em] mb-4">
        {title}
      </h3>
      <div className="space-y-2">
        {seeds.map((s, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="font-display text-sm font-bold text-text-muted w-6 text-center">#{i + 1}</span>
            <TeamSelector
              teams={teams}
              value={s}
              onChange={(v) => onSeed(i, v)}
              label=""
              excludeAbbr=""
            />
            {usedAbbrs.filter((a) => a === s).length > 1 && s && (
              <span className="text-loss text-xs">Duplicate</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ConferenceBracket({ title, data }: { title: string; data: BracketState['afc'] }) {
  return (
    <div className="space-y-4">
      <h3 className="font-display text-sm font-semibold text-text-primary uppercase tracking-wider">{title}</h3>
      {data.wildCard.length > 0 && <RoundCard title="Wild Card" matchups={data.wildCard} />}
      {data.divisional.length > 0 && <RoundCard title="Divisional" matchups={data.divisional} />}
      {data.conference && <RoundCard title={`${title} Championship`} matchups={[data.conference]} />}
    </div>
  );
}

function RoundCard({ title, matchups }: { title: string; matchups: MatchupResult[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface-850 overflow-hidden">
      <div className="px-4 py-2.5 bg-surface-800/50 border-b border-border">
        <span className="font-display text-[10px] font-semibold text-text-muted uppercase tracking-[0.15em]">
          {title}
        </span>
      </div>
      <div className="divide-y divide-border">
        {matchups.map((m, i) => {
          const hc = getTeamColors(m.home).primary;
          const ac = getTeamColors(m.away).primary;
          return (
            <div key={i} className="flex items-center px-4 py-3 gap-3">
              <div className="flex-1 flex items-center gap-2">
                <span
                  className="w-7 h-7 rounded-sm flex items-center justify-center text-[9px] font-display font-bold text-white"
                  style={{ backgroundColor: ac }}
                >{m.away}</span>
                <span className="text-xs tabular-nums text-text-secondary">{(m.awayProb * 100).toFixed(0)}%</span>
              </div>
              <span className="text-text-muted text-xs font-display">@</span>
              <div className="flex-1 flex items-center gap-2 justify-end">
                <span className="text-xs tabular-nums text-text-secondary">{(m.homeProb * 100).toFixed(0)}%</span>
                <span
                  className="w-7 h-7 rounded-sm flex items-center justify-center text-[9px] font-display font-bold text-white"
                  style={{ backgroundColor: hc }}
                >{m.home}</span>
              </div>
              <span
                className="ml-3 font-display text-xs font-bold px-2 py-1 rounded"
                style={{ color: getTeamColors(m.winner).primary, backgroundColor: `${getTeamColors(m.winner).primary}15` }}
              >
                {m.winner}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
