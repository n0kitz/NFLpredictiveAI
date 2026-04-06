"""Database connection and management for NFL Prediction System."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "nfl.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    """SQLite database connection manager for NFL data."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Uses default if not provided.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self._connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> 'Database':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        try:
            yield self.connection
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Transaction failed: {e}")
            raise

    def init_schema(self) -> None:
        """Initialize database schema from schema.sql file."""
        logger.info(f"Initializing database schema from {SCHEMA_PATH}")

        with open(SCHEMA_PATH, 'r') as f:
            schema_sql = f.read()

        with self.transaction():
            self.connection.executescript(schema_sql)

        logger.info("Database schema initialized successfully")

    def execute(self, query: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Execute a single query."""
        return self.connection.execute(query, params)

    def executemany(self, query: str, params_list: List[Tuple]) -> sqlite3.Cursor:
        """Execute a query with multiple parameter sets."""
        return self.connection.executemany(query, params_list)

    def fetchone(self, query: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
        """Execute query and fetch one result."""
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def fetchall(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute query and fetch all results."""
        cursor = self.execute(query, params)
        return cursor.fetchall()

    def commit(self) -> None:
        """Commit current transaction."""
        self.connection.commit()

    # Team operations
    def insert_team(self, name: str, city: str, conference: str, division: str,
                    abbreviation: str, franchise_id: Optional[str] = None,
                    active_from: Optional[int] = None,
                    active_until: Optional[int] = None) -> int:
        """
        Insert a new team into the database.

        Returns:
            The team_id of the inserted team.
        """
        query = """
            INSERT INTO teams (name, city, conference, division, abbreviation,
                             franchise_id, active_from, active_until)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = self.execute(query, (name, city, conference, division, abbreviation,
                                       franchise_id, active_from, active_until))
        self.commit()
        return cursor.lastrowid

    def get_team_by_abbreviation(self, abbreviation: str) -> Optional[sqlite3.Row]:
        """Get team by abbreviation."""
        query = "SELECT * FROM teams WHERE abbreviation = ?"
        return self.fetchone(query, (abbreviation,))

    def get_team_by_id(self, team_id: int) -> Optional[sqlite3.Row]:
        """Get team by ID."""
        query = "SELECT * FROM teams WHERE team_id = ?"
        return self.fetchone(query, (team_id,))

    def get_all_teams(self, active_only: bool = True) -> List[sqlite3.Row]:
        """Get all teams, optionally filtered to active teams only."""
        if active_only:
            query = "SELECT * FROM current_teams ORDER BY conference, division, name"
        else:
            query = "SELECT * FROM teams ORDER BY conference, division, name"
        return self.fetchall(query)

    def find_team(self, search_term: str) -> Optional[sqlite3.Row]:
        """
        Find a team by name, city, or abbreviation (case-insensitive).

        Args:
            search_term: Team name, city, or abbreviation to search for.

        Returns:
            Team row if found, None otherwise.
        """
        search_term = search_term.strip().upper()

        # Try abbreviation first (exact match)
        team = self.fetchone(
            "SELECT * FROM teams WHERE UPPER(abbreviation) = ? AND active_until IS NULL",
            (search_term,)
        )
        if team:
            return team

        # Try name (partial match)
        team = self.fetchone(
            "SELECT * FROM teams WHERE UPPER(name) LIKE ? AND active_until IS NULL",
            (f"%{search_term}%",)
        )
        if team:
            return team

        # Try city (partial match)
        team = self.fetchone(
            "SELECT * FROM teams WHERE UPPER(city) LIKE ? AND active_until IS NULL",
            (f"%{search_term}%",)
        )
        return team

    # Game operations
    def insert_game(self, date: str, season: int, week: str, game_type: str,
                    home_team_id: int, away_team_id: int,
                    home_score: Optional[int] = None,
                    away_score: Optional[int] = None,
                    winner_id: Optional[int] = None,
                    venue: Optional[str] = None,
                    attendance: Optional[int] = None,
                    overtime: bool = False) -> int:
        """
        Insert a new game into the database.

        Returns:
            The game_id of the inserted game.
        """
        query = """
            INSERT OR IGNORE INTO games
            (date, season, week, game_type, home_team_id, away_team_id,
             home_score, away_score, winner_id, venue, attendance, overtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = self.execute(query, (date, season, week, game_type, home_team_id,
                                       away_team_id, home_score, away_score,
                                       winner_id, venue, attendance, overtime))
        self.commit()
        return cursor.lastrowid

    def get_games_by_season(self, season: int,
                            game_type: Optional[str] = None) -> List[sqlite3.Row]:
        """Get all games for a season, optionally filtered by game type."""
        if game_type:
            query = """
                SELECT * FROM game_details
                WHERE season = ? AND game_type = ?
                ORDER BY date
            """
            return self.fetchall(query, (season, game_type))
        else:
            query = "SELECT * FROM game_details WHERE season = ? ORDER BY date"
            return self.fetchall(query, (season,))

    def get_team_games(self, team_id: int, season: Optional[int] = None,
                       limit: Optional[int] = None) -> List[sqlite3.Row]:
        """Get games for a specific team."""
        query = """
            SELECT g.*,
                   ht.name AS home_team, ht.abbreviation AS home_abbr,
                   at.name AS away_team, at.abbreviation AS away_abbr,
                   wt.name AS winner, wt.abbreviation AS winner_abbr
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            LEFT JOIN teams wt ON g.winner_id = wt.team_id
            WHERE (g.home_team_id = ? OR g.away_team_id = ?)
        """
        params: List[Any] = [team_id, team_id]

        if season:
            query += " AND g.season = ?"
            params.append(season)

        query += " ORDER BY g.date DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        return self.fetchall(query, tuple(params))

    def get_head_to_head(self, team1_id: int, team2_id: int,
                         limit: Optional[int] = None) -> List[sqlite3.Row]:
        """Get head-to-head games between two teams."""
        query = """
            SELECT g.*,
                   ht.name AS home_team, ht.abbreviation AS home_abbr,
                   at.name AS away_team, at.abbreviation AS away_abbr,
                   wt.name AS winner, wt.abbreviation AS winner_abbr
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            LEFT JOIN teams wt ON g.winner_id = wt.team_id
            WHERE (g.home_team_id = ? AND g.away_team_id = ?)
               OR (g.home_team_id = ? AND g.away_team_id = ?)
            ORDER BY g.date DESC
        """
        params: List[Any] = [team1_id, team2_id, team2_id, team1_id]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        return self.fetchall(query, tuple(params))

    def get_playoff_games(self, team_id: int) -> List[sqlite3.Row]:
        """Get all playoff games for a team."""
        query = """
            SELECT g.*,
                   ht.name AS home_team, ht.abbreviation AS home_abbr,
                   at.name AS away_team, at.abbreviation AS away_abbr,
                   wt.name AS winner, wt.abbreviation AS winner_abbr
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            LEFT JOIN teams wt ON g.winner_id = wt.team_id
            WHERE g.game_type = 'playoff'
              AND (g.home_team_id = ? OR g.away_team_id = ?)
            ORDER BY g.date DESC
        """
        return self.fetchall(query, (team_id, team_id))

    # Team season stats operations
    def upsert_team_season_stats(self, team_id: int, season: int,
                                  stats: Dict[str, Any]) -> None:
        """Insert or update team season statistics."""
        query = """
            INSERT INTO team_season_stats
            (team_id, season, games_played, wins, losses, ties,
             points_for, points_against, point_differential,
             home_wins, home_losses, home_ties, away_wins, away_losses, away_ties,
             win_percentage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, season) DO UPDATE SET
                games_played = excluded.games_played,
                wins = excluded.wins,
                losses = excluded.losses,
                ties = excluded.ties,
                points_for = excluded.points_for,
                points_against = excluded.points_against,
                point_differential = excluded.point_differential,
                home_wins = excluded.home_wins,
                home_losses = excluded.home_losses,
                home_ties = excluded.home_ties,
                away_wins = excluded.away_wins,
                away_losses = excluded.away_losses,
                away_ties = excluded.away_ties,
                win_percentage = excluded.win_percentage,
                last_updated = CURRENT_TIMESTAMP
        """
        self.execute(query, (
            team_id, season,
            stats.get('games_played', 0),
            stats.get('wins', 0),
            stats.get('losses', 0),
            stats.get('ties', 0),
            stats.get('points_for', 0),
            stats.get('points_against', 0),
            stats.get('point_differential', 0),
            stats.get('home_wins', 0),
            stats.get('home_losses', 0),
            stats.get('home_ties', 0),
            stats.get('away_wins', 0),
            stats.get('away_losses', 0),
            stats.get('away_ties', 0),
            stats.get('win_percentage', 0.0)
        ))
        self.commit()

    def get_team_season_stats(self, team_id: int,
                               season: Optional[int] = None) -> List[sqlite3.Row]:
        """Get team season statistics."""
        if season:
            query = """
                SELECT * FROM team_season_stats
                WHERE team_id = ? AND season = ?
            """
            return self.fetchall(query, (team_id, season))
        else:
            query = """
                SELECT * FROM team_season_stats
                WHERE team_id = ?
                ORDER BY season DESC
            """
            return self.fetchall(query, (team_id,))

    # Game factors operations
    def insert_game_factor(self, game_id: int, team_id: int, factor_type: str,
                           factor_value: Optional[str] = None,
                           impact_rating: int = 0) -> int:
        """Insert a game factor."""
        query = """
            INSERT INTO game_factors (game_id, team_id, factor_type, factor_value, impact_rating)
            VALUES (?, ?, ?, ?, ?)
        """
        cursor = self.execute(query, (game_id, team_id, factor_type,
                                       factor_value, impact_rating))
        self.commit()
        return cursor.lastrowid

    def get_game_factors(self, game_id: int) -> List[sqlite3.Row]:
        """Get all factors for a game."""
        query = """
            SELECT gf.*, t.name AS team_name, t.abbreviation AS team_abbr
            FROM game_factors gf
            JOIN teams t ON gf.team_id = t.team_id
            WHERE gf.game_id = ?
            ORDER BY gf.created_at
        """
        return self.fetchall(query, (game_id,))

    def remove_game_factor(self, factor_id: int) -> bool:
        """Remove a game factor by ID."""
        query = "DELETE FROM game_factors WHERE factor_id = ?"
        cursor = self.execute(query, (factor_id,))
        self.commit()
        return cursor.rowcount > 0

    # Scrape progress tracking
    def get_scrape_status(self, season: int, week: str) -> Optional[str]:
        """Get scraping status for a season/week."""
        query = "SELECT status FROM scrape_progress WHERE season = ? AND week = ?"
        result = self.fetchone(query, (season, week))
        return result['status'] if result else None

    def update_scrape_status(self, season: int, week: str, status: str,
                              error_message: Optional[str] = None) -> None:
        """Update scraping status for a season/week."""
        query = """
            INSERT INTO scrape_progress (season, week, status, last_attempt, error_message)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(season, week) DO UPDATE SET
                status = excluded.status,
                last_attempt = CURRENT_TIMESTAMP,
                error_message = excluded.error_message
        """
        self.execute(query, (season, week, status, error_message))
        self.commit()

    def get_incomplete_scrapes(self) -> List[sqlite3.Row]:
        """Get all incomplete scrape tasks."""
        query = """
            SELECT * FROM scrape_progress
            WHERE status IN ('pending', 'in_progress', 'failed')
            ORDER BY season, week
        """
        return self.fetchall(query)

    def calculate_team_season_stats(self, season: int) -> None:
        """Calculate and store team season statistics from game data."""
        teams = self.get_all_teams(active_only=False)

        for team in teams:
            team_id = team['team_id']
            games = self.get_team_games(team_id, season)

            if not games:
                continue

            stats = {
                'games_played': 0,
                'wins': 0,
                'losses': 0,
                'ties': 0,
                'points_for': 0,
                'points_against': 0,
                'home_wins': 0,
                'home_losses': 0,
                'home_ties': 0,
                'away_wins': 0,
                'away_losses': 0,
                'away_ties': 0,
            }

            for game in games:
                if game['home_score'] is None or game['away_score'] is None:
                    continue

                stats['games_played'] += 1
                is_home = game['home_team_id'] == team_id

                if is_home:
                    stats['points_for'] += game['home_score']
                    stats['points_against'] += game['away_score']
                else:
                    stats['points_for'] += game['away_score']
                    stats['points_against'] += game['home_score']

                # Determine win/loss/tie
                if game['winner_id'] == team_id:
                    stats['wins'] += 1
                    if is_home:
                        stats['home_wins'] += 1
                    else:
                        stats['away_wins'] += 1
                elif game['winner_id'] is None:
                    stats['ties'] += 1
                    if is_home:
                        stats['home_ties'] += 1
                    else:
                        stats['away_ties'] += 1
                else:
                    stats['losses'] += 1
                    if is_home:
                        stats['home_losses'] += 1
                    else:
                        stats['away_losses'] += 1

            stats['point_differential'] = stats['points_for'] - stats['points_against']

            if stats['games_played'] > 0:
                stats['win_percentage'] = (
                    stats['wins'] + 0.5 * stats['ties']
                ) / stats['games_played']

            self.upsert_team_season_stats(team_id, season, stats)


# Singleton instance (CLI usage)
_database: Optional[Database] = None


def get_database(db_path: Optional[Path] = None) -> Database:
    """Get the database singleton instance. Use for CLI only."""
    global _database
    if _database is None:
        _database = Database(db_path)
    return _database


def create_database(db_path: Optional[Path] = None) -> Database:
    """Create a new Database instance. Use for web server (one per request)."""
    return Database(db_path)
