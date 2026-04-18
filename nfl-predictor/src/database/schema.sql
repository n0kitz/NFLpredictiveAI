-- NFL Prediction System Database Schema
-- SQLite compatible

-- Teams table
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    conference TEXT CHECK(conference IN ('AFC', 'NFC')),
    division TEXT NOT NULL,
    abbreviation TEXT NOT NULL UNIQUE,
    -- Track historical names for the same franchise
    franchise_id TEXT,  -- Groups teams that are the same franchise (e.g., 'STL_LA_RAMS')
    active_from INTEGER,  -- Year this name/city started
    active_until INTEGER,  -- Year this name/city ended (NULL if current)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Games table
CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    season INTEGER NOT NULL,
    week TEXT NOT NULL,  -- 1-18 for regular season, 'Wild Card', 'Divisional', 'Conference', 'Super Bowl'
    game_type TEXT CHECK(game_type IN ('regular', 'playoff')) DEFAULT 'regular',
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    winner_id INTEGER,  -- NULL for ties
    venue TEXT,
    attendance INTEGER,
    overtime BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (winner_id) REFERENCES teams(team_id),
    UNIQUE(date, home_team_id, away_team_id)
);

-- Game factors table (for future use - initially empty)
CREATE TABLE IF NOT EXISTS game_factors (
    factor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    factor_type TEXT NOT NULL CHECK(factor_type IN (
        'better_defense', 'bad_defense',
        'better_offense', 'bad_offense',
        'better_qb', 'qb_struggles',
        'turnover_prone', 'turnover_forcing',
        'not_efficient', 'highly_efficient',
        'injury_impact', 'weather_impact',
        'coaching_advantage', 'motivation_factor',
        'custom'
    )),
    factor_value TEXT,  -- Text description or rating
    impact_rating INTEGER CHECK(impact_rating BETWEEN -5 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

-- Team season stats (derived/aggregated)
CREATE TABLE IF NOT EXISTS team_season_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    games_played INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    ties INTEGER DEFAULT 0,
    points_for INTEGER DEFAULT 0,
    points_against INTEGER DEFAULT 0,
    point_differential INTEGER DEFAULT 0,
    home_wins INTEGER DEFAULT 0,
    home_losses INTEGER DEFAULT 0,
    home_ties INTEGER DEFAULT 0,
    away_wins INTEGER DEFAULT 0,
    away_losses INTEGER DEFAULT 0,
    away_ties INTEGER DEFAULT 0,
    win_percentage REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    UNIQUE(team_id, season)
);

-- Scraping progress tracking (for resumable scraping)
CREATE TABLE IF NOT EXISTS scrape_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    week TEXT NOT NULL,
    status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')) DEFAULT 'pending',
    last_attempt TIMESTAMP,
    error_message TEXT,
    UNIQUE(season, week)
);

-- Prediction history (auto-saved from /api/predict)
CREATE TABLE IF NOT EXISTS prediction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    predicted_winner_id INTEGER NOT NULL,
    home_prob REAL NOT NULL,
    away_prob REAL NOT NULL,
    confidence TEXT NOT NULL,
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    game_id INTEGER,  -- nullable, matched after game is played
    actual_winner_id INTEGER,  -- filled in by enrichment
    correct INTEGER,  -- 1/0/null
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (predicted_winner_id) REFERENCES teams(team_id),
    FOREIGN KEY (actual_winner_id) REFERENCES teams(team_id)
);

-- Advanced team stats (imported from nfl_data_py / nflverse)
CREATE TABLE IF NOT EXISTS team_advanced_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    turnover_margin REAL DEFAULT 0,
    third_down_pct REAL DEFAULT 0,
    redzone_efficiency REAL DEFAULT 0,
    yards_per_play REAL DEFAULT 0,
    sack_rate_allowed REAL DEFAULT 0,
    UNIQUE(team_id, season),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

-- Injury reports (from ESPN public API)
CREATE TABLE IF NOT EXISTS injury_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    position TEXT NOT NULL,
    injury_status TEXT NOT NULL,
    report_date TEXT NOT NULL,
    UNIQUE(team_id, player_name, report_date),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

-- Game weather conditions (from Open-Meteo)
CREATE TABLE IF NOT EXISTS game_weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    home_team_id INTEGER,
    game_date TEXT NOT NULL,
    is_dome INTEGER NOT NULL DEFAULT 0,
    temperature_c REAL,
    wind_speed_kmh REAL,
    precipitation_mm REAL,
    weather_code INTEGER,
    condition TEXT,
    is_adverse INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT,
    UNIQUE(home_team_id, game_date),
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id)
);

-- Vegas betting odds (from The Odds API)
CREATE TABLE IF NOT EXISTS game_odds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    external_game_id TEXT,
    home_team_id INTEGER,
    away_team_id INTEGER,
    game_date TEXT,
    opening_spread REAL,
    over_under REAL,
    home_implied_prob REAL,
    away_implied_prob REAL,
    fetched_at TEXT,
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    UNIQUE(external_game_id)
);

-- Players (scraped from ESPN roster API)
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    espn_id TEXT UNIQUE,
    full_name TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    position TEXT,
    jersey_number TEXT,
    date_of_birth TEXT,
    height_cm REAL,
    weight_kg REAL,
    college TEXT,
    experience_years INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Active',
    headshot_url TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- Roster entries (player <-> team <-> season)
CREATE TABLE IF NOT EXISTS roster_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    depth_position TEXT,
    is_starter INTEGER DEFAULT 0,
    roster_status TEXT,
    fetched_at TEXT,
    UNIQUE(player_id, team_id, season),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

-- Player season stats (from nfl_data_py seasonal data)
CREATE TABLE IF NOT EXISTS player_season_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    games_played INTEGER DEFAULT 0,
    pass_attempts INTEGER DEFAULT 0,
    pass_completions INTEGER DEFAULT 0,
    pass_yards INTEGER DEFAULT 0,
    pass_tds INTEGER DEFAULT 0,
    interceptions INTEGER DEFAULT 0,
    passer_rating REAL DEFAULT 0,
    rush_attempts INTEGER DEFAULT 0,
    rush_yards INTEGER DEFAULT 0,
    rush_tds INTEGER DEFAULT 0,
    yards_per_carry REAL DEFAULT 0,
    targets INTEGER DEFAULT 0,
    receptions INTEGER DEFAULT 0,
    rec_yards INTEGER DEFAULT 0,
    rec_tds INTEGER DEFAULT 0,
    yards_per_reception REAL DEFAULT 0,
    tackles INTEGER DEFAULT 0,
    sacks REAL DEFAULT 0,
    interceptions_def INTEGER DEFAULT 0,
    fantasy_points_ppr REAL DEFAULT 0,
    fantasy_points_standard REAL DEFAULT 0,
    UNIQUE(player_id, team_id, season),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

-- ── Fantasy module tables ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fantasy_leagues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    scoring_format TEXT NOT NULL DEFAULT 'ppr',
    roster_slots TEXT NOT NULL DEFAULT '{"QB":1,"RB":2,"WR":2,"TE":1,"FLEX":1,"BN":6}',
    waiver_type TEXT DEFAULT 'faab',
    season INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fantasy_rosters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id INTEGER NOT NULL REFERENCES fantasy_leagues(id),
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    slot TEXT NOT NULL,
    acquired_week INTEGER,
    acquired_type TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fantasy_projections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    opponent_team_id INTEGER REFERENCES teams(team_id),
    projected_points_ppr REAL,
    projected_points_std REAL,
    matchup_score REAL,
    opportunity_score REAL,
    confidence TEXT DEFAULT 'medium',
    -- Phase 1 ML additions
    model_version TEXT,                -- e.g. 'ml-v1-WR', or null for heuristic
    model_source TEXT DEFAULT 'heuristic',  -- 'heuristic' | 'ml'
    floor_ppr REAL,                    -- P10 (placeholder until Phase 2)
    ceiling_ppr REAL,                  -- P90 (placeholder until Phase 2)
    contributions_json TEXT,           -- JSON list of top SHAP contributions
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season, week)
);

CREATE TABLE IF NOT EXISTS draft_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    scoring_format TEXT NOT NULL,
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    overall_rank INTEGER,
    position_rank INTEGER,
    tier INTEGER,
    adp REAL,
    projected_season_points REAL,
    notes TEXT,
    UNIQUE(season, scoring_format, player_id)
);

-- Weekly per-player stats (nfl_data_py weekly import) — powers ML player projections
CREATE TABLE IF NOT EXISTS player_weekly_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    team_id INTEGER REFERENCES teams(team_id),
    opponent_team_id INTEGER REFERENCES teams(team_id),
    position TEXT,
    is_home INTEGER DEFAULT 0,
    snaps INTEGER DEFAULT 0,
    snap_pct REAL DEFAULT 0,
    routes INTEGER DEFAULT 0,
    route_pct REAL DEFAULT 0,
    targets INTEGER DEFAULT 0,
    receptions INTEGER DEFAULT 0,
    rec_yards INTEGER DEFAULT 0,
    rec_tds INTEGER DEFAULT 0,
    target_share REAL DEFAULT 0,
    air_yards INTEGER DEFAULT 0,
    adot REAL DEFAULT 0,
    rush_attempts INTEGER DEFAULT 0,
    rush_yards INTEGER DEFAULT 0,
    rush_tds INTEGER DEFAULT 0,
    pass_attempts INTEGER DEFAULT 0,
    pass_completions INTEGER DEFAULT 0,
    pass_yards INTEGER DEFAULT 0,
    pass_tds INTEGER DEFAULT 0,
    interceptions INTEGER DEFAULT 0,
    fantasy_points_ppr REAL DEFAULT 0,
    fantasy_points_standard REAL DEFAULT 0,
    UNIQUE(player_id, season, week)
);
CREATE INDEX IF NOT EXISTS idx_player_weekly_season_week ON player_weekly_stats(season, week);
CREATE INDEX IF NOT EXISTS idx_player_weekly_player ON player_weekly_stats(player_id, season, week DESC);
CREATE INDEX IF NOT EXISTS idx_player_weekly_opp ON player_weekly_stats(opponent_team_id, season, week);

-- Weekly QB starts (per-game starter EPA, used for rolling 4-game feature)
CREATE TABLE IF NOT EXISTS weekly_qb_starts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    player_id INTEGER REFERENCES players(player_id),
    qb_name TEXT,
    epa_per_play REAL,
    snap_count INTEGER,
    UNIQUE(team_id, season, week)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);
CREATE INDEX IF NOT EXISTS idx_games_teams ON games(home_team_id, away_team_id);
CREATE INDEX IF NOT EXISTS idx_games_winner ON games(winner_id);
CREATE INDEX IF NOT EXISTS idx_game_factors_game ON game_factors(game_id);
CREATE INDEX IF NOT EXISTS idx_game_factors_team ON game_factors(team_id);
CREATE INDEX IF NOT EXISTS idx_team_stats_season ON team_season_stats(team_id, season);
CREATE INDEX IF NOT EXISTS idx_teams_abbr ON teams(abbreviation);
CREATE INDEX IF NOT EXISTS idx_teams_franchise ON teams(franchise_id);
CREATE INDEX IF NOT EXISTS idx_prediction_history_date ON prediction_history(predicted_at);
CREATE INDEX IF NOT EXISTS idx_games_home_date ON games(home_team_id, date);
CREATE INDEX IF NOT EXISTS idx_games_away_date ON games(away_team_id, date);
CREATE INDEX IF NOT EXISTS idx_odds_teams ON game_odds(home_team_id, away_team_id, game_date);
CREATE INDEX IF NOT EXISTS idx_weekly_qb ON weekly_qb_starts(team_id, season, week DESC);
CREATE INDEX IF NOT EXISTS idx_inj_team ON injury_reports(team_id, report_date DESC);
CREATE INDEX IF NOT EXISTS idx_pred_hist_teams ON prediction_history(home_team_id, away_team_id);

-- Views for common queries

-- Current teams view (only active teams)
CREATE VIEW IF NOT EXISTS current_teams AS
SELECT * FROM teams WHERE active_until IS NULL;

-- Game details view with team names
CREATE VIEW IF NOT EXISTS game_details AS
SELECT
    g.game_id,
    g.date,
    g.season,
    g.week,
    g.game_type,
    ht.name AS home_team,
    ht.abbreviation AS home_abbr,
    at.name AS away_team,
    at.abbreviation AS away_abbr,
    g.home_score,
    g.away_score,
    wt.name AS winner,
    wt.abbreviation AS winner_abbr,
    g.venue,
    g.attendance,
    g.overtime
FROM games g
JOIN teams ht ON g.home_team_id = ht.team_id
JOIN teams at ON g.away_team_id = at.team_id
LEFT JOIN teams wt ON g.winner_id = wt.team_id;
