import { useState, useRef, useEffect, useCallback } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { PlayerSearchResult } from '../api/types';

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

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
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
          className="w-44 bg-surface-800 border border-border rounded-md pl-8 pr-3 py-1.5 text-xs text-text-secondary placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
        />
      </div>
      {open && results.length > 0 && (
        <div className="absolute right-0 top-full mt-1 w-64 rounded-xl border border-border bg-surface-850 shadow-2xl z-50 overflow-hidden">
          {results.map((p) => (
            <button
              key={p.player_id}
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

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Top nav — broadcast ticker style */}
      <header className="sticky top-0 z-50 border-b border-border bg-surface-900/90 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 flex items-center h-14 gap-0">
          {/* Logo */}
          <NavLink to="/" className="flex items-center gap-3 mr-8 group">
            <div className="relative">
              <div className="w-8 h-8 rounded-sm bg-accent flex items-center justify-center rotate-[-2deg] group-hover:rotate-0 transition-transform duration-300">
                <span className="font-display font-bold text-surface-900 text-sm tracking-tight">
                  NFL
                </span>
              </div>
            </div>
            <span className="font-display font-semibold text-text-primary text-lg tracking-wide uppercase hidden sm:block">
              Predictor
            </span>
          </NavLink>

          {/* Nav links */}
          <nav className="flex items-center h-full">
            {NAV_ITEMS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `relative h-full flex items-center px-5 font-display text-sm font-medium uppercase tracking-widest transition-colors ${
                    isActive
                      ? 'text-accent'
                      : 'text-text-muted hover:text-text-secondary'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {label}
                    {isActive && (
                      <span className="absolute bottom-0 left-4 right-4 h-[2px] bg-accent rounded-full" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Right side — player search + data badge */}
          <div className="ml-auto flex items-center gap-4">
            <PlayerSearch />
            <div className="hidden md:flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-win animate-pulse" />
              <span className="text-[11px] text-text-muted font-medium tracking-wide">
                9,400+ GAMES
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-10">
        <Outlet />
      </main>

      {/* Footer — minimal broadcast bar */}
      <footer className="border-t border-border">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <span className="text-[11px] text-text-muted font-display uppercase tracking-widest">
            NFL Predictor
          </span>
          <span className="text-[11px] text-text-muted">
            35 seasons of data &middot; 1990&ndash;2025
          </span>
        </div>
      </footer>
    </div>
  );
}
