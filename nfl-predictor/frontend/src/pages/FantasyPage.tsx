import { useState } from 'react';
import DashboardTab from './fantasy/DashboardTab';
import LeaderboardsTab from './fantasy/LeaderboardsTab';
import WaiverTab from './fantasy/WaiverTab';
import DraftTab from './fantasy/DraftTab';
import TradeTabWithValues from './fantasy/TradeTab';
import PowerRankingsTab from './fantasy/PowerRankingsTab';
import OptimizerTab from './fantasy/OptimizerTab';
import RosterImportHelper from './fantasy/RosterImportHelper';

const TABS = ['Dashboard', 'Leaderboards', 'Waiver Wire', 'Draft', 'Trade Analyzer', 'Power Rankings', 'Optimizer'] as const;
type Tab = typeof TABS[number];

export default function FantasyPage() {
  const [active, setActive] = useState<Tab>('Dashboard');
  const [rosterIds, setRosterIds] = useState<number[]>([]);

  return (
    <div className="animate-fade-up">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold text-text-primary tracking-tight">
          Fantasy Football
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Projections · Draft rankings · Trade analysis · Waiver wire · Power rankings
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-border mb-8 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActive(tab)}
            className={`relative px-4 py-3 font-display text-sm font-medium uppercase tracking-widest transition-colors whitespace-nowrap shrink-0 ${
              active === tab ? 'text-accent' : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {tab}
            {active === tab && (
              <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-accent rounded-full" />
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {active === 'Dashboard' && (
        <div className="space-y-6">
          <DashboardTab />
          <RosterImportHelper onImported={setRosterIds} />
          {rosterIds.length > 0 && (
            <p className="text-xs text-win">Roster set — {rosterIds.length} players imported.</p>
          )}
        </div>
      )}
      {active === 'Leaderboards'   && <LeaderboardsTab />}
      {active === 'Waiver Wire'    && <WaiverTab />}
      {active === 'Draft'          && <DraftTab />}
      {active === 'Trade Analyzer' && <TradeTabWithValues />}
      {active === 'Power Rankings' && <PowerRankingsTab />}
      {active === 'Optimizer'      && <OptimizerTab />}
    </div>
  );
}
