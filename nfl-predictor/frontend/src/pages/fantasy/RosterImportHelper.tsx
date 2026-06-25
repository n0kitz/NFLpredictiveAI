import { useState } from 'react';
import { api } from '../../api/client';
import type { RosterMatchEntry } from '../../api/types';
import { LAST_COMPLETED_SEASON } from '../../config';

export default function RosterImportHelper({ onImported }: { onImported: (ids: number[]) => void }) {
  const [text, setText] = useState('');
  const [matched, setMatched] = useState<RosterMatchEntry[]>([]);
  const [unmatched, setUnmatched] = useState<string[]>([]);
  const [step, setStep] = useState<'input' | 'confirm'>('input');
  const [loading, setLoading] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

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
