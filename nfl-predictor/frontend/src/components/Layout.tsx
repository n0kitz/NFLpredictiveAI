import { useState, useRef, useEffect, useCallback } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { PlayerSearchResult } from '../api/types';
import Ticker from './Ticker';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/predict', label: 'Predict' },
  { to: '/teams', label: 'Teams' },
  { to: '/compare', label: 'Compare' },
  { to: '/seasons', label: 'Seasons' },
  { to: '/history', label: 'History' },
  { to: '/playoffs', label: 'Playoffs' },
  { to: '/fantasy', label: 'Fantasy' },
];

function PlayerSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PlayerSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback((q: string) => {
    if (q.length < 2) { setResults([]); setOpen(false); return; }
    api.searchPlayers(q).then((r) => {
      setResults(r.slice(0, 8));
      setOpen(r.length > 0);
    }).catch(() => setResults([]));
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => search(q), 250);
  }

  function pick(p: PlayerSearchResult) {
    setQuery('');
    setResults([]);
    setOpen(false);
    navigate(`/players/${p.player_id}`);
  }

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handler);
    return () => {
      document.removeEventListener('mousedown', handler);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35m0 0A7.5 7.5 0 1 0 5.25 5.25a7.5 7.5 0 0 0 10.4 10.4z" />
        </svg>
        <input
          value={query}
          onChange={handleChange}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Search players…"
          aria-label="Search NFL players"
          aria-autocomplete="list"
          aria-haspopup="listbox"
          className="w-44 bg-surface-700 border border-border rounded-sm pl-8 pr-3 py-1.5 text-xs text-text-secondary placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
        />
      </div>
      {open && results.length > 0 && (
        <div role="listbox" aria-label="Player search results" className="absolute right-0 top-full mt-1 w-64 rounded-xl border border-border bg-surface-850 shadow-2xl z-50 overflow-hidden">
          {results.map((p) => (
            <button
              key={p.player_id}
              role="option"
              aria-selected={false}
              onMouseDown={() => pick(p)}
              className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-surface-700 transition-colors text-left"
            >
              {p.headshot_url ? (
                <img src={p.headshot_url} alt={p.full_name} className="w-7 h-7 rounded-full object-cover shrink-0 bg-surface-700"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
              ) : (
                <div className="w-7 h-7 rounded-full bg-surface-700 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-text-primary truncate">{p.full_name}</p>
                <p className="text-[10px] text-text-muted">{p.position ?? '—'} · {p.team_abbr ?? '—'}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function useModelStatus() {
  const [online, setOnline] = useState<boolean | null>(null);
  const [dataUpdatedAt, setDataUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    api.health()
      .then((h) => {
        setOnline(true);
        // h may be typed as HealthStatus (old type alias) but now includes data_updated_at
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setDataUpdatedAt((h as any).data_updated_at ?? null);
      })
      .catch(() => setOnline(false));
  }, []);

  // Compute staleness
  const isStale = dataUpdatedAt !== null && (() => {
    const updated = new Date(dataUpdatedAt).getTime();
    const now = Date.now();
    return (now - updated) > 7 * 24 * 60 * 60 * 1000;
  })();

  return { online, dataUpdatedAt, isStale };
}

export default function Layout() {
  const { online: modelOnline, dataUpdatedAt, isStale } = useModelStatus();
  return (
    <div className="min-h-screen flex flex-col">
      {/* Sticky header: TopBar + Ticker */}
      <header className="sticky top-0 z-50">
        {/* TopBar */}
        <div className="bg-surface-850 border-b border-border">
          <div className="px-6 flex items-center h-14 gap-0">
            {/* Logo */}
            <NavLink to="/" className="flex items-center mr-8 shrink-0">
              <span className="font-display font-extrabold text-[18px] tracking-tight leading-none">
                <span className="text-accent">▲</span>
                {' '}NFL<span className="text-text-muted">/</span>PREDICTOR
              </span>
            </NavLink>

            {/* Nav pills */}
            <nav className="flex items-center gap-0.5 font-display text-[12px] font-semibold tracking-[0.08em]">
              {NAV_ITEMS.map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `px-3.5 py-2 rounded-sm transition-colors uppercase ${
                      isActive
                        ? 'bg-surface-700 text-text-primary'
                        : 'text-text-muted hover:text-text-secondary'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>

            {/* Right side */}
            <div className="ml-auto flex items-center gap-3">
              <PlayerSearch />
              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-surface-700 rounded-sm font-display text-[11px] font-semibold tracking-[0.1em] shrink-0">
                <div className={`w-1.5 h-1.5 rounded-full ${modelOnline === false ? 'bg-red-500' : 'bg-win animate-pulse'}`} />
                {modelOnline === false ? 'MODEL OFFLINE' : 'MODEL ONLINE'}
              </div>
            </div>
          </div>
        </div>

        {/* Ticker */}
        <Ticker />
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-12">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <span className="text-[11px] text-text-muted font-display uppercase tracking-widest">
            NFL Predictor
          </span>
          <div className="flex items-center gap-4">
            {isStale && (
              <span className="text-[10px] text-yellow-500 font-semibold uppercase tracking-wider">
                ⚠ Data may be stale
              </span>
            )}
            {dataUpdatedAt && (
              <span className="text-[11px] text-text-muted">
                Stats as of {dataUpdatedAt}
              </span>
            )}
            <span className="text-[11px] text-text-muted">
              35 seasons &middot; 1990&ndash;2025
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
