import { NavLink, Outlet } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/predict', label: 'Predict' },
  { to: '/teams', label: 'Teams' },
  { to: '/compare', label: 'Compare' },
  { to: '/seasons', label: 'Seasons' },
  { to: '/history', label: 'History' },
  { to: '/playoffs', label: 'Playoffs' },
];

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

          {/* Right side — data badge */}
          <div className="ml-auto flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-win animate-pulse" />
            <span className="text-[11px] text-text-muted font-medium tracking-wide">
              9,400+ GAMES
            </span>
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
