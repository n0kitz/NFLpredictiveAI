import { useState } from 'react';
import { ACTIVE_SEASON } from '../config';
import { loadMyRoster, saveMyRoster } from './fantasy/myRoster';
import DashboardTab from './fantasy/DashboardTab';
import LeaderboardsTab from './fantasy/LeaderboardsTab';
import WaiverTab from './fantasy/WaiverTab';
import DraftTab from './fantasy/DraftTab';
import TradeTabWithValues from './fantasy/TradeTab';
import PowerRankingsTab from './fantasy/PowerRankingsTab';
import OptimizerTab from './fantasy/OptimizerTab';
import RosterImportHelper from './fantasy/RosterImportHelper';
import MyTeamTab from './fantasy/MyTeamTab';
import ScheduleTab from './fantasy/ScheduleTab';
import WeeklyBriefingTab from './fantasy/WeeklyBriefingTab';

const TABS = ['Weekly Briefing', 'My Team', 'Schedule', 'Dashboard', 'Leaderboards', 'Waiver Wire', 'Draft', 'Trade Analyzer', 'Power Rankings', 'Optimizer'] as const;
type Tab = typeof TABS[number];

export default function FantasyPage() {
  const [active, setActive] = useState<Tab>('Weekly Briefing');
  // Persisted per season so the imported roster survives reloads
  const [rosterIds, setRosterIds] = useState<number[]>(() => loadMyRoster(ACTIVE_SEASON));
  const updateRoster = (ids: number[]) => {
    setRosterIds(ids);
    saveMyRoster(ACTIVE_SEASON, ids);
  };

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
          <RosterImportHelper onImported={updateRoster} />
          {rosterIds.length > 0 && (
            <p className="text-xs text-win">Roster set — {rosterIds.length} players imported (saved).</p>
          )}
        </div>
      )}
      {active === 'Weekly Briefing' && <WeeklyBriefingTab rosterIds={rosterIds} onImported={updateRoster} />}
      {active === 'My Team'        && <MyTeamTab rosterIds={rosterIds} onImported={updateRoster} />}
      {active === 'Schedule'       && <ScheduleTab rosterIds={rosterIds} onImported={updateRoster} />}
      {active === 'Leaderboards'   && <LeaderboardsTab />}
      {active === 'Waiver Wire'    && <WaiverTab excludeIds={rosterIds} />}
      {active === 'Draft'          && <DraftTab />}
      {active === 'Trade Analyzer' && <TradeTabWithValues />}
      {active === 'Power Rankings' && <PowerRankingsTab />}
      {active === 'Optimizer'      && <OptimizerTab />}
    </div>
  );
}
