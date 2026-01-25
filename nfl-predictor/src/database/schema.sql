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
