/** TypeScript types matching the FastAPI Pydantic schemas exactly. */

export interface Team {
  team_id: number;
  name: string;
  city: string;
  conference: string;
  division: string;
  abbreviation: string;
  franchise_id: string | null;
  active_from: number | null;
  active_until: number | null;
}

export interface TeamList {
  teams: Team[];
  count: number;
}

export interface Game {
  game_id: number;
  date: string;
  season: number;
  week: string;
  game_type: string;
  home_team_id: number;
  away_team_id: number;
  home_team: string | null;
  home_abbr: string | null;
  away_team: string | null;
  away_abbr: string | null;
  home_score: number | null;
  away_score: number | null;
  winner: string | null;
  winner_abbr: string | null;
  winner_id: number | null;
  overtime: boolean;
}

export interface GameList {
  games: Game[];
  count: number;
  team?: string;
}

export interface AppliedFactor {
  factor_type: string;
  team_abbr: string | null;
  impact_rating: number;
}

export interface Prediction {
  home_team: string;
  away_team: string;
  home_team_id: number;
  away_team_id: number;
  home_win_probability: number;
  away_win_probability: number;
  predicted_winner: string;
  predicted_winner_probability: number;
  confidence: 'low' | 'medium' | 'high';
  key_factors: string[];
  factors_applied: AppliedFactor[];
}

export interface H2H {
  team1_name: string;
  team1_abbr: string;
  team2_name: string;
  team2_abbr: string;
  team1_wins: number;
  team2_wins: number;
  ties: number;
  total_games: number;
  games: Game[];
}

export interface TeamMetrics {
  team_id: number;
  team_name: string;
  team_abbr: string;
  current_season_wins: number;
  current_season_losses: number;
  current_season_ties: number;
  win_percentage: number;
  avg_points_scored: number;
  avg_points_allowed: number;
  point_differential: number;
  home_wins: number;
  home_losses: number;
  away_wins: number;
  away_losses: number;
  home_win_pct: number;
  away_win_pct: number;
  recent_wins: number;
  recent_losses: number;
  recent_win_pct: number;
  offensive_strength: number;
  defensive_strength: number;
  strength_of_schedule: number;
  dynamic_hfa: number;
  rest_days: number;
  games_analyzed: number;
}

export interface TeamSeasonStats {
  team_id: number;
  team_name: string;
  season: number;
  games_played: number;
  wins: number;
  losses: number;
  ties: number;
  win_percentage: number;
  points_for: number;
  points_against: number;
  point_differential: number;
  home_wins: number;
  home_losses: number;
  away_wins: number;
  away_losses: number;
}

export interface TeamProfileStats {
  wins: number;
  losses: number;
  ties: number;
  win_pct: number;
  games_played: number;
  points_for: number;
  points_against: number;
  point_differential: number;
  home_wins: number;
  home_losses: number;
  away_wins: number;
  away_losses: number;
  ppg: number;
  papg: number;
}

export interface TeamProfile {
  team_id: number;
  team_name: string;
  team_abbr: string;
  all_time: TeamProfileStats;
  last_season: TeamProfileStats | null;
  last_season_year: number | null;
}

export interface HealthStatus {
  status: string;
  total_teams: number;
  total_games: number;
  database: string;
}

export interface InlineFactor {
  factor_type: string;
  team: 'home' | 'away';
  impact_rating: number;
}

export interface PredictionHistoryItem {
  id: number;
  home_abbr: string;
  away_abbr: string;
  home_team: string;
  away_team: string;
  predicted_winner_abbr: string;
  home_prob: number;
  away_prob: number;
  confidence: string;
  predicted_at: string;
  actual_winner_abbr: string | null;
  correct: boolean | null;
}

export interface PredictionHistory {
  predictions: PredictionHistoryItem[];
  total: number;
  resolved: number;
  correct: number;
  accuracy: number | null;
}

export interface ExplanationEntry {
  feature: string;
  label: string;
  shap_value: number;
  direction: 'home' | 'away' | 'neutral';
  feature_value: number;
}

export interface PredictionExplanation extends Prediction {
  explanation: ExplanationEntry[];
}

export interface PlayerStatsEntry {
  games_played: number;
  pass_attempts: number;
  pass_completions: number;
  pass_yards: number;
  pass_tds: number;
  interceptions: number;
  passer_rating: number;
  rush_attempts: number;
  rush_yards: number;
  rush_tds: number;
  yards_per_carry: number;
  targets: number;
  receptions: number;
  rec_yards: number;
  rec_tds: number;
  yards_per_reception: number;
  fantasy_points_ppr: number;
  fantasy_points_standard: number;
}

export interface PlayerEntry {
  player_id: number;
  espn_id: string | null;
  full_name: string;
  position: string | null;
  jersey_number: string | null;
  depth_position: string | null;
  is_starter: boolean;
  roster_status: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  college: string | null;
  experience_years: number;
  headshot_url: string | null;
  stats: PlayerStatsEntry | null;
}

export interface TeamRoster {
  team_id: number;
  team_abbr: string;
  season: number;
  players: PlayerEntry[];
  count: number;
}

export interface PlayerProfile {
  player_id: number;
  espn_id: string | null;
  full_name: string;
  first_name: string | null;
  last_name: string | null;
  position: string | null;
  jersey_number: string | null;
  date_of_birth: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  college: string | null;
  experience_years: number;
  status: string | null;
  headshot_url: string | null;
  team_abbr: string | null;
  current_stats: PlayerStatsEntry | null;
}

export interface PlayerSearchResult {
  player_id: number;
  full_name: string;
  position: string | null;
  team_abbr: string | null;
  jersey_number: string | null;
  headshot_url: string | null;
}

export interface FantasyPlayerEntry {
  player_id: number;
  full_name: string;
  position: string | null;
  team_abbr: string | null;
  headshot_url: string | null;
  games_played: number;
  fantasy_points_ppr: number;
  fantasy_points_standard: number;
  points_per_game_ppr: number;
}

export interface FantasyLeaderboard {
  position: string;
  season: number;
  scoring: string;
  players: FantasyPlayerEntry[];
  count: number;
}

export interface AccuracyStats {
  seasons: number[];
  total_games: number;
  correct_predictions: number;
  accuracy: number;
  by_confidence: Record<string, { total: number; correct: number; accuracy: number }>;
  calibration: Record<string, { total: number; correct: number }>;
  season_accuracy: Record<string, { total: number; correct: number; accuracy: number }>;
}
