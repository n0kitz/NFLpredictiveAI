import { useState } from 'react';
import { api } from '../../api/client';
import type { NflLeagueSync, RosterMatchEntry } from '../../api/types';
import { LAST_COMPLETED_SEASON } from '../../config';
import { saveLeagueSettings, type Scoring } from './leagueSettings';

export default function RosterImportHelper({ onImported }: { onImported: (ids: number[]) => void }) {
  const [text, setText] = useState('');
  const [matched, setMatched] = useState<RosterMatchEntry[]>([]);
  const [unmatched, setUnmatched] = useState<string[]>([]);
  const [step, setStep] = useState<'input' | 'confirm'>('input');
  const [loading, setLoading] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [leagueId, setLeagueId] = useState('');
  const [syncTeams, setSyncTeams] = useState<NflLeagueSync['teams']>([]);
  const [syncNote, setSyncNote] = useState<string | null>(null);

  async function handleNflSync() {
    if (!leagueId.trim()) return;
    setLoading(true);
    setImportError(null);
    setSyncNote(null);
    try {
      const res = await api.getNflLeagueSync(leagueId.trim());
      saveLeagueSettings({
        scoring: res.settings.scoring as Scoring,
        leagueSize: res.settings.league_size,
      });
      setSyncTeams(res.teams);
      setSyncNote(
        `Synced "${res.settings.name}" — ${res.settings.league_size} teams, ` +
        `${res.settings.scoring} scoring applied. Pick your team below.`
      );
    } catch (err: unknown) {
      setImportError(err instanceof Error
        ? `NFL.com sync failed: ${err.message}`
        : 'NFL.com sync failed — use manual paste instead.');
    } finally {
      setLoading(false);
    }
  }

  function adoptSyncTeam(players: [string, string][]) {
    setText(players.map(([name]) => name).join('\n'));
    setSyncTeams([]);
    setSyncNote('Team roster loaded into the box below — hit Find Players.');
  }

  async function handleSearch() {
    const names = text.split('\n').map((n) => n.trim()).filter(Boolean);
    if (!names.length) return;
    setLoading(true);
    setImportError(null);
    try {
      const res = await api.importRosterByNames(names, LAST_COMPLETED_SEASON);
      setMatched(res.matched);
      setUnmatched(res.unmatched);
      setStep('confirm');
    } catch (err: unknown) {
      setImportError(err instanceof Error ? err.message : 'Import failed');
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
      {importError && <p className="text-red-400 text-xs">{importError}</p>}
      {step === 'input' ? (
        <>
          <div className="flex items-center gap-2 flex-wrap">
            <input
              value={leagueId}
              onChange={(e) => setLeagueId(e.target.value)}
              placeholder="NFL.com league ID"
              className="bg-surface-800 border border-border rounded px-3 py-1.5 text-xs text-text-secondary placeholder:text-text-muted focus:outline-none focus:border-accent w-40"
            />
            <button onClick={handleNflSync} disabled={loading || !leagueId.trim()}
              className="px-3 py-1.5 rounded border border-border text-[10px] font-display font-bold uppercase tracking-widest text-text-muted hover:text-text-secondary disabled:opacity-40">
              Sync from NFL.com
            </button>
            <span className="text-[9px] text-amber-400/80 uppercase tracking-wide">experimental — needs server-side cookie</span>
          </div>
          {syncNote && <p className="text-xs text-win">{syncNote}</p>}
          {syncTeams.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {syncTeams.map((t) => (
                <button key={t.team_id} onClick={() => adoptSyncTeam(t.players)}
                  className="px-3 py-1.5 rounded border border-border text-xs text-text-secondary hover:border-accent">
                  {t.team_name} ({t.players.length})
                </button>
              ))}
            </div>
          )}
          <p className="text-xs text-text-muted">Or paste your NFL.com roster player names (one per line) to enable Start/Sit recommendations.</p>
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
