import { Link } from 'react-router-dom';
import TeamLogo from './TeamLogo';
import type { PlayoffConference, PlayoffTeamEntry } from '../api/types';

// ── helpers ───────────────────────────────────────────────────────────────────

function getSeededTeams(conf: PlayoffConference): PlayoffTeamEntry[] {
  const all = [
    ...Object.values(conf.divisions).flat(),
    ...conf.wildcard,
  ];
  // Dedupe by abbr
  const seen = new Set<string>();
  const unique = all.filter((t) => {
    if (seen.has(t.team_abbr)) return false;
    seen.add(t.team_abbr);
    return true;
  });
  return unique
    .filter((t) => t.seed !== null && t.clinched !== 'eliminated')
    .sort((a, b) => (a.seed ?? 99) - (b.seed ?? 99))
    .slice(0, 7);
}

// ── sub-components ────────────────────────────────────────────────────────────

function SeedSlot({
  team,
  dim = false,
  bye = false,
}: {
  team: PlayoffTeamEntry | null;
  dim?: boolean;
  bye?: boolean;
}) {
  if (!team) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-800/50 border border-border/40 opacity-40">
        <span className="w-5 text-[10px] font-bold text-text-muted text-center">?</span>
        <span className="text-xs text-text-muted">TBD</span>
      </div>
    );
  }

  const record = `${team.wins}-${team.losses}${team.ties > 0 ? `-${team.ties}` : ''}`;

  return (
    <Link
      to={`/teams/${team.team_abbr}`}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors hover:bg-surface-700/50 ${
        dim ? 'opacity-50 border-border/30 bg-surface-800/30' : 'border-border/60 bg-surface-800/60'
      }`}
    >
      <span className="w-5 text-[10px] font-display font-bold text-text-muted text-center shrink-0">
        {team.seed}
      </span>
      <TeamLogo abbr={team.team_abbr} size={20} className="rounded-sm" />
      <span className="text-xs font-semibold text-text-primary truncate flex-1">
        {team.team_abbr}
      </span>
      <span className="text-[10px] text-text-muted tabular-nums shrink-0">{record}</span>
      {bye && (
        <span className="text-[9px] font-display font-bold px-1.5 py-0.5 rounded bg-accent/15 text-accent uppercase shrink-0">
          BYE
        </span>
      )}
      {team.clinched === 'division' && (
        <span className="text-[9px] font-display font-bold px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 uppercase shrink-0">
          DIV
        </span>
      )}
    </Link>
  );
}

function Matchup({
  top,
  bottom,
  label,
}: {
  top: PlayoffTeamEntry | null;
  bottom: PlayoffTeamEntry | null;
  label?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-850 overflow-hidden">
      {label && (
        <div className="px-3 py-1.5 bg-surface-800/60 border-b border-border">
          <span className="text-[10px] font-display font-semibold text-text-muted uppercase tracking-widest">
            {label}
          </span>
        </div>
      )}
      <div className="p-2 space-y-1">
        <SeedSlot team={top} />
        <div className="h-px bg-border/50 mx-2" />
        <SeedSlot team={bottom} />
      </div>
    </div>
  );
}

function ConferenceColumn({
  label,
  seeds,
}: {
  label: string;
  seeds: PlayoffTeamEntry[];
}) {
  const seed = (n: number) => seeds.find((t) => t.seed === n) ?? null;

  return (
    <div className="flex-1 min-w-0">
      {/* Conference label */}
      <div className="flex items-center gap-2 mb-3">
        <div className="h-px flex-1 bg-border" />
        <span className="font-display text-[11px] font-bold uppercase tracking-[0.2em] text-text-muted">
          {label}
        </span>
        <div className="h-px flex-1 bg-border" />
      </div>

      {/* Seed 1 — bye */}
      <div className="mb-3">
        <p className="text-[9px] font-display uppercase tracking-widest text-text-muted mb-1.5 px-1">
          First-Round Bye
        </p>
        <SeedSlot team={seed(1)} bye />
      </div>

      {/* Wild card matchups */}
      <div className="space-y-2">
        <p className="text-[9px] font-display uppercase tracking-widest text-text-muted px-1">
          Wild Card
        </p>
        <Matchup top={seed(2)} bottom={seed(7)} />
        <Matchup top={seed(3)} bottom={seed(6)} />
        <Matchup top={seed(4)} bottom={seed(5)} />
      </div>
    </div>
  );
}

// ── main export ───────────────────────────────────────────────────────────────

export default function PlayoffBracket({
  afc,
  nfc,
}: {
  afc: PlayoffConference;
  nfc: PlayoffConference;
}) {
  const afcSeeds = getSeededTeams(afc);
  const nfcSeeds = getSeededTeams(nfc);

  if (afcSeeds.length === 0 && nfcSeeds.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-surface-900/50 p-5">
      <div className="flex items-center gap-2 mb-5">
        <div className="h-px w-6 bg-accent" />
        <span className="font-display text-[11px] uppercase tracking-[0.2em] text-accent font-semibold">
          Projected Bracket
        </span>
        <div className="flex-1 h-px bg-border" />
      </div>

      <div className="flex gap-4 items-start">
        <ConferenceColumn label="AFC" seeds={afcSeeds} />

        {/* Super Bowl center */}
        <div className="flex flex-col items-center gap-2 pt-16 px-2 shrink-0">
          <div className="w-px h-8 bg-accent/30" />
          <div className="rounded-full w-8 h-8 border-2 border-accent/40 flex items-center justify-center">
            <span className="text-[8px] font-display font-bold text-accent uppercase">SB</span>
          </div>
          <div className="w-px h-8 bg-accent/30" />
        </div>

        <ConferenceColumn label="NFC" seeds={nfcSeeds} />
      </div>

      <p className="text-[10px] text-text-muted mt-4 text-center">
        Matchups projected from current seedings — subject to change.
      </p>
    </div>
  );
}
