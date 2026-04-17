/**
 * NFL Team color definitions.
 *
 * Each team has a `primary` and `secondary` color.
 * These are used for cards, accents, probability bars, etc.
 * Keyed by the team abbreviation returned from the API.
 *
 * To re-theme the app, swap the hex values here — nothing else changes.
 */

export interface TeamColor {
  primary: string;
  secondary: string;
}

export const TEAM_COLORS: Record<string, TeamColor> = {
  // AFC East
  BUF: { primary: '#00338D', secondary: '#C60C30' },
  MIA: { primary: '#008E97', secondary: '#FC4C02' },
  NE:  { primary: '#002244', secondary: '#C60C30' },
  NYJ: { primary: '#125740', secondary: '#FFFFFF' },

  // AFC North
  BAL: { primary: '#241773', secondary: '#9E7C0C' },
  CIN: { primary: '#FB4F14', secondary: '#000000' },
  CLE: { primary: '#311D00', secondary: '#FF3C00' },
  PIT: { primary: '#FFB612', secondary: '#101820' },

  // AFC South
  HOU: { primary: '#03202F', secondary: '#A71930' },
  IND: { primary: '#002C5F', secondary: '#A2AAAD' },
  JAX: { primary: '#006778', secondary: '#D7A22A' },
  TEN: { primary: '#0C2340', secondary: '#4B92DB' },

  // AFC West
  DEN: { primary: '#FB4F14', secondary: '#002244' },
  KC:  { primary: '#E31837', secondary: '#FFB81C' },
  LV:  { primary: '#000000', secondary: '#A5ACAF' },
  LAC: { primary: '#0080C6', secondary: '#FFC20E' },

  // NFC East
  DAL: { primary: '#041E42', secondary: '#869397' },
  NYG: { primary: '#0B2265', secondary: '#A71930' },
  PHI: { primary: '#004C54', secondary: '#A5ACAF' },
  WAS: { primary: '#5A1414', secondary: '#FFB612' },

  // NFC North
  CHI: { primary: '#0B162A', secondary: '#C83803' },
  DET: { primary: '#0076B6', secondary: '#B0B7BC' },
  GB:  { primary: '#203731', secondary: '#FFB612' },
  MIN: { primary: '#4F2683', secondary: '#FFC62F' },

  // NFC South
  ATL: { primary: '#A71930', secondary: '#000000' },
  CAR: { primary: '#0085CA', secondary: '#101820' },
  NO:  { primary: '#D3BC8D', secondary: '#101820' },
  TB:  { primary: '#D50A0A', secondary: '#FF7900' },

  // NFC West
  ARI: { primary: '#97233F', secondary: '#000000' },
  LAR: { primary: '#003594', secondary: '#FFA300' },
  SF:  { primary: '#AA0000', secondary: '#B3995D' },
  SEA: { primary: '#002244', secondary: '#69BE28' },
};

/** Get team colors with a safe fallback */
export function getTeamColors(abbr: string): TeamColor {
  return TEAM_COLORS[abbr] ?? { primary: '#4f8cff', secondary: '#1a1e2e' };
}

/**
 * Return a CSS linear-gradient string for a team.
 * Useful for card headers, progress bars, etc.
 */
export function teamGradient(abbr: string, direction = 'to right'): string {
  const c = getTeamColors(abbr);
  return `linear-gradient(${direction}, ${c.primary}, ${c.secondary})`;
}

/**
 * Return a subtle background with team color tint.
 * Good for card backgrounds — just a hint of team color.
 */
export function teamBgTint(abbr: string, opacity = 0.12): string {
  const c = getTeamColors(abbr);
  return hexToRgba(c.primary, opacity);
}

/**
 * ESPN CDN overrides: internal abbr → ESPN abbr (lowercase).
 * Only needed when the ESPN abbr differs from the internal one.
 */
const ESPN_ABBR_OVERRIDES: Record<string, string> = {
  JAX: 'jax',
  LAR: 'lar',
  WAS: 'was',
};

/**
 * Return the ESPN CDN logo URL for a team abbreviation.
 * Falls back gracefully if the abbr is unknown.
 */
export function getTeamLogoUrl(abbr: string): string {
  const espn = ESPN_ABBR_OVERRIDES[abbr] ?? abbr.toLowerCase();
  return `https://a.espncdn.com/i/teamlogos/nfl/500/${espn}.png`;
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
