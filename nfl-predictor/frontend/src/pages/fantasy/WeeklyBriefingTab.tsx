import { useState } from 'react';
import { api } from '../../api/client';
import type {
  LineupAdvice, PlayerScheduleOutlook, StreamingCandidate, FaabCandidate,
} from '../../api/types';
import { ACTIVE_SEASON } from '../../config';
import { useLeagueSettings } from './leagueSettings';
import RosterImportHelper from './RosterImportHelper';

interface Props {
  rosterIds: number[];
  onImported: (ids: number[]) => void;
}

async function settle<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

/**
 * "What do I change this week?" — pure composition of My Team, Schedule,
 * Streaming and FAAB. No new math: every number here comes from an
 * endpoint that already exists and is already tested.
 */
export default function WeeklyBriefingTab({ rosterIds, onImported }: Props) {
  const [{ scoring, leagueSize }] = useLeagueSettings();
  const [week, setWeek] = useState(1);
  const [lineup, setLineup] = useState<LineupAdvice | null>(null);
  const [byeWeekPlayers, setByeWeekPlayers] = useState<PlayerScheduleOutlook[]>([]);
  const [streamPick, setStreamPick] = useState<StreamingCandidate | null>(null);
  const [faabTarget, setFaabTarget] = useState<FaabCandidate | null>(null);
  const [loading, setLoading] = useState(false);
  const [generated, setGenerated] = useState(false);

  async function generate() {
    if (rosterIds.length === 0) return;
    setLoading(true);
    setGenerated(false);
    const [lineupRes, outlookRes, streamRes, faabRes] = await Promise.all([
      settle(api.getMyTeamLineup(rosterIds, week, ACTIVE_SEASON, undefined, scoring, leagueSize)),
      settle(api.getScheduleOutlook(rosterIds, ACTIVE_SEASON, [week])),
      settle(api.getStreamingCandidates('DST', week, ACTIVE_SEASON, rosterIds, 1)),
      settle(api.getFaabRecommendations(rosterIds, week, ACTIVE_SEASON, 'all', scoring, leagueSize, 100, 1)),
    ]);

    setLineup(lineupRes);
    setByeWeekPlayers(
      outlookRes ? outlookRes.players.filter((p) => p.bye_week === week) : [],
    );
    setStreamPick(streamRes?.candidates[0] ?? null);
    setFaabTarget(faabRes?.candidates[0] ?? null);
    setLoading(false);
    setGenerated(true);
  }

  if (rosterIds.length === 0) {
    return (
      <div className="space-y-6">
        <p className="text-sm text-text-muted">
          Import your roster to get one composed view of everything worth
          checking before you set your lineup this week.
        </p>
        <RosterImportHelper onImported={onImported} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-xs uppercase tracking-widest text-text-muted">
          Week
          <select
            aria-label="Week"
            value={week}
            onChange={(e) => setWeek(Number(e.target.value))}
            className="mt-1 block bg-surface-800 border border-border rounded px-3 py-2 text-sm text-text-primary"
          >
            {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
              <option key={w} value={w}>{w}</option>
            ))}
          </select>
        </label>
        <button
          onClick={generate}
          disabled={loading}
          className="px-4 py-2 rounded bg-accent text-surface-900 font-display text-sm font-semibold uppercase tracking-widest disabled:opacity-50"
        >
          {loading ? 'Working…' : 'Generate briefing'}
        </button>
      </div>

      {generated && (
        <div className="space-y-6">
          {byeWeekPlayers.length > 0 && (
            <div className="rounded border border-loss/40 px-3 py-2">
              <p className="text-sm text-loss font-semibold">On bye this week</p>
              {byeWeekPlayers.map((p) => (
                <p key={p.player_id} className="text-sm text-text-secondary">
                  {p.full_name} ({p.position}) — bye
                </p>
              ))}
            </div>
          )}

          <div>
            <h3 className="font-display text-sm font-semibold uppercase tracking-widest text-text-primary">
              Your lineup
            </h3>
            {!lineup ? (
              <p className="text-xs text-text-muted mt-2">Lineup data unavailable.</p>
            ) : lineup.swaps.length === 0 ? (
              <p className="text-sm text-win mt-2">Already optimal — no changes needed.</p>
            ) : (
              <ul className="mt-2 space-y-1.5">
                {lineup.swaps.map((s) => (
                  <li key={`${s.start_player_id}-${s.sit_player_id}`} className="text-sm">
                    <span className="text-win font-semibold">Start {s.start_name}</span>{' '}
                    over {s.sit_name}{' '}
                    <span className="text-text-muted">(+{s.point_delta.toFixed(1)} pts)</span>
                  </li>
                ))}
              </ul>
            )}
            {lineup?.warnings.map((w) => (
              <p key={w} className="text-sm text-loss mt-1">⚠ {w}</p>
            ))}
          </div>

          <div>
            <h3 className="font-display text-sm font-semibold uppercase tracking-widest text-text-primary">
              Top streaming pick (DST)
            </h3>
            {!streamPick ? (
              <p className="text-xs text-text-muted mt-2">No streaming data available.</p>
            ) : (
              <p className="text-sm mt-2">
                {streamPick.full_name} ({streamPick.team_abbr} vs {streamPick.opponent_team_abbr}) — grade {streamPick.grade}
              </p>
            )}
          </div>

          <div>
            <h3 className="font-display text-sm font-semibold uppercase tracking-widest text-text-primary">
              Top FAAB target
            </h3>
            {!faabTarget ? (
              <p className="text-xs text-text-muted mt-2">No waiver target clears your replacement level.</p>
            ) : (
              <p className="text-sm mt-2">
                {faabTarget.full_name} ({faabTarget.position}) — {faabTarget.tier}, suggest {faabTarget.suggested_bid_pct}% (${faabTarget.suggested_bid_amount})
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
