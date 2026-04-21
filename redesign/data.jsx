// Shared data — fictional league, teams, matchups, value picks.
// All original — no real NFL branding.

const TEAMS = {
  REB: { name: 'Rebels',   city: 'New York',    primary: '#C8102E', secondary: '#0A1A2F' },
  VLT: { name: 'Voltage',  city: 'Los Angeles', primary: '#FFD400', secondary: '#111111' },
  IRN: { name: 'Ironmen',  city: 'Pittsburgh',  primary: '#F2A900', secondary: '#1C1C1C' },
  TDL: { name: 'Tidal',    city: 'Miami',       primary: '#00B2A9', secondary: '#0A1D2F' },
  TMB: { name: 'Timber',   city: 'Portland',    primary: '#3E6B3A', secondary: '#2A1E14' },
  BLZ: { name: 'Blaze',    city: 'Phoenix',     primary: '#FF6B1A', secondary: '#2A0F07' },
  SNT: { name: 'Sentinel', city: 'Chicago',     primary: '#1F4E8C', secondary: '#0E1A2E' },
  WRS: { name: 'Warriors', city: 'Kansas City', primary: '#8A2BE2', secondary: '#1C0E2E' },
  OKS: { name: 'Oaks',     city: 'Atlanta',     primary: '#5A7F3F', secondary: '#1A2310' },
  GLC: { name: 'Glacier',  city: 'Denver',      primary: '#6FAEDB', secondary: '#0E2033' },
  CRW: { name: 'Crown',    city: 'Seattle',     primary: '#B38E3F', secondary: '#1A140A' },
  HRK: { name: 'Harrier',  city: 'Dallas',      primary: '#D23F57', secondary: '#2A0E14' },
};

// Week matchups — [away, home, awayPct]
const MATCHUPS = [
  { away: 'REB', home: 'VLT', awayPct: 58, status: 'FRI 8:20',  edge: 'MODEL +4.5', confidence: 'HIGH',   spread: '-3.5', ou: 48.5 },
  { away: 'IRN', home: 'TDL', awayPct: 43, status: 'SUN 1:00',  edge: 'MODEL +1.8', confidence: 'MEDIUM', spread: '+2.5', ou: 44.0 },
  { away: 'TMB', home: 'BLZ', awayPct: 71, status: 'SUN 1:00',  edge: 'MODEL +6.2', confidence: 'HIGH',   spread: '-5.5', ou: 41.5 },
  { away: 'SNT', home: 'WRS', awayPct: 34, status: 'SUN 4:25',  edge: 'FADE',       confidence: 'MEDIUM', spread: '+4.5', ou: 46.0 },
  { away: 'OKS', home: 'GLC', awayPct: 52, status: 'SUN 4:25',  edge: 'LEAN',       confidence: 'LOW',    spread: '+1.5', ou: 43.5 },
  { away: 'CRW', home: 'HRK', awayPct: 47, status: 'SUN 8:20',  edge: 'MODEL +0.9', confidence: 'LOW',    spread: '+2.0', ou: 49.5 },
  { away: 'VLT', home: 'WRS', awayPct: 61, status: 'MON 8:15',  edge: 'MODEL +3.1', confidence: 'HIGH',   spread: '-2.5', ou: 47.0 },
  { away: 'TDL', home: 'BLZ', awayPct: 39, status: 'THU 8:20',  edge: 'FADE',       confidence: 'MEDIUM', spread: '+3.5', ou: 45.0 },
];

const HERO_MATCHUP = {
  away: 'REB', home: 'VLT', awayPct: 58,
  venue: 'Continental Field · Los Angeles',
  kickoff: 'Fri, Apr 24 · 8:20 PM ET',
  week: 'Week 12',
  broadcast: 'Prime Feed',
  spread: 'VLT -3.5',
  total: 'O/U 48.5',
  weather: '68°F · Clear · 4mph W',
  awayRecord: '8-3',
  homeRecord: '9-2',
  factors: [
    { label: 'Offensive Efficiency', away: 72, home: 81 },
    { label: 'Defensive Rating',     away: 68, home: 74 },
    { label: 'Recent Form (L5)',     away: 80, home: 60 },
    { label: 'Head-to-Head (10y)',   away: 55, home: 45 },
    { label: 'Rest & Travel',        away: 50, home: 70 },
    { label: 'Weather Adjustment',   away: 62, home: 62 },
  ],
  trend: [52, 49, 51, 54, 56, 55, 57, 58, 56, 58, 59, 58],
};

const VALUE_PICKS = [
  { name: 'Darius Kline',    pos: 'WR', team: 'BLZ', proj: 14.2, own: 6,  edge: '+4.8', tag: 'SLEEPER' },
  { name: 'Theo Marchetti',  pos: 'RB', team: 'TMB', proj: 18.6, own: 11, edge: '+5.2', tag: 'CORE' },
  { name: 'Jax Kowalski',    pos: 'QB', team: 'SNT', proj: 22.1, own: 18, edge: '+3.1', tag: 'VALUE' },
  { name: 'Rhett Aldana',    pos: 'TE', team: 'CRW', proj: 11.8, own: 4,  edge: '+6.0', tag: 'SLEEPER' },
  { name: 'Mateo Silverio',  pos: 'WR', team: 'REB', proj: 16.4, own: 22, edge: '+2.4', tag: 'VALUE' },
  { name: 'Kwame Okafor',    pos: 'RB', team: 'HRK', proj: 15.9, own: 9,  edge: '+4.1', tag: 'SLEEPER' },
  { name: 'Nik Varga',       pos: 'WR', team: 'GLC', proj: 13.2, own: 7,  edge: '+3.8', tag: 'SLEEPER' },
  { name: 'Luca Pennington',  pos: 'QB', team: 'VLT', proj: 24.8, own: 31, edge: '+2.9', tag: 'CORE' },
];

const ACCURACY = {
  season: 0.672,
  l5: 0.71,
  correct: 139,
  total: 207,
  high: { correct: 48, total: 61 },
  medium: { correct: 62, total: 98 },
  low: { correct: 29, total: 48 },
};

const STANDINGS_BRIEF = [
  { abbr: 'VLT', w: 9, l: 2, streak: 'W4', pf: 312, pa: 241 },
  { abbr: 'REB', w: 8, l: 3, streak: 'W2', pf: 289, pa: 234 },
  { abbr: 'TMB', w: 8, l: 3, streak: 'L1', pf: 276, pa: 228 },
  { abbr: 'WRS', w: 7, l: 4, streak: 'W1', pf: 298, pa: 251 },
  { abbr: 'GLC', w: 7, l: 4, streak: 'W3', pf: 271, pa: 244 },
  { abbr: 'HRK', w: 6, l: 5, streak: 'L2', pf: 262, pa: 258 },
];

Object.assign(window, { TEAMS, MATCHUPS, HERO_MATCHUP, VALUE_PICKS, ACCURACY, STANDINGS_BRIEF });
