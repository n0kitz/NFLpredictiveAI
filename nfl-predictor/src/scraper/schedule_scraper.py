"""ESPN schedule scraper — fetches upcoming + completed game schedule via public ESPN API.

No auth required. Maps ESPN team names to DB abbreviations via ESPN_TEAM_MAP.
Inserts new games into the `games` table (skips duplicates).
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from .injury_scraper import ESPN_TEAM_MAP  # reuse existing mapping

logger = logging.getLogger(__name__)

# ESPN scoreboard API — works for any week/season without auth
_ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
)
_REQUEST_TIMEOUT = 10
_RATE_LIMIT = 1.5  # seconds between requests


# ESPN uses full team names; build reverse lookup: espn_abbr → db_abbr
_ESPN_ABBR_TO_DB: Dict[str, str] = {
    "ARI": "ARI", "ATL": "ATL", "BAL": "BAL", "BUF": "BUF",
    "CAR": "CAR", "CHI": "CHI", "CIN": "CIN", "CLE": "CLE",
    "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GB": "GB",
    "HOU": "HOU", "IND": "IND", "JAX": "JAX", "KC": "KC",
    "LV": "LV",  "LAC": "LAC", "LA": "LAR", "LAR": "LAR",
    "MIA": "MIA", "MIN": "MIN", "NE": "NE",  "NO": "NO",
    "NYG": "NYG", "NYJ": "NYJ", "PHI": "PHI", "PIT": "PIT",
    "SF": "SF",  "SEA": "SEA", "TB": "TB",  "TEN": "TEN",
    "WSH": "WAS", "WAS": "WAS",
}


def _map_abbr(espn_abbr: str) -> Optional[str]:
    """Convert ESPN team abbreviation to DB abbreviation."""
    return _ESPN_ABBR_TO_DB.get(espn_abbr.upper())


class ScheduleScraper:
    """Fetches NFL schedule from ESPN public API and upserts into `games` table."""

    def __init__(self, db=None) -> None:
        self.db = db
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; NFL-Predictor)"})

    def fetch_week(self, season: int, week: int, season_type: int = 2) -> List[Dict[str, Any]]:
        """
        Fetch games for a specific week from ESPN.

        Args:
            season: Season year (e.g. 2025)
            week: Week number (1-18 for regular season, 1-4 for playoffs)
            season_type: 1=preseason, 2=regular, 3=playoffs

        Returns:
            List of game dicts with keys matching `games` table schema.
        """
        params = {
            "limit": 50,
            "seasontype": season_type,
            "week": week,
            "dates": season,
        }
        try:
            resp = self._session.get(_ESPN_SCOREBOARD, params=params, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("ESPN scoreboard request failed (week=%d, season=%d): %s", week, season, exc)
            return []

        data = resp.json()
        games = []
        for event in data.get("events", []):
            game = self._parse_event(event, season, week, season_type)
            if game:
                games.append(game)
        return games

    def fetch_season(self, season: int) -> List[Dict[str, Any]]:
        """Fetch all regular-season games (weeks 1-18) for a season."""
        all_games: List[Dict[str, Any]] = []
        for week in range(1, 19):
            games = self.fetch_week(season, week, season_type=2)
            all_games.extend(games)
            if games:
                logger.info("ESPN schedule: season=%d week=%d → %d games", season, week, len(games))
            time.sleep(_RATE_LIMIT)
        # Also fetch playoffs (4 rounds max)
        for week in range(1, 5):
            games = self.fetch_week(season, week, season_type=3)
            all_games.extend(games)
            if games:
                logger.info("ESPN schedule: season=%d playoff_week=%d → %d games", season, week, len(games))
            time.sleep(_RATE_LIMIT)
        return all_games

    def _parse_event(self, event: dict, season: int, week: int, season_type: int) -> Optional[Dict[str, Any]]:
        """Parse a single ESPN event into a DB-compatible dict."""
        try:
            competitions = event.get("competitions", [])
            if not competitions:
                return None
            comp = competitions[0]

            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                return None

            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                return None

            home_espn = home["team"]["abbreviation"]
            away_espn = away["team"]["abbreviation"]
            home_abbr = _map_abbr(home_espn)
            away_abbr = _map_abbr(away_espn)
            if not home_abbr or not away_abbr:
                logger.debug("Unknown ESPN abbr: home=%s away=%s", home_espn, away_espn)
                return None

            # Parse date (ESPN returns ISO 8601 UTC)
            date_raw = event.get("date", "")
            try:
                dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                game_date = dt.strftime("%Y-%m-%d")
            except (ValueError, AttributeError):
                game_date = date_raw[:10]

            # Scores — None if game is not completed
            home_score: Optional[int] = None
            away_score: Optional[int] = None
            winner_abbr: Optional[str] = None
            status = comp.get("status", {}).get("type", {}).get("name", "")
            if status in ("STATUS_FINAL", "STATUS_FINAL_OT"):
                try:
                    home_score = int(home.get("score", 0))
                    away_score = int(away.get("score", 0))
                    if home_score > away_score:
                        winner_abbr = home_abbr
                    elif away_score > home_score:
                        winner_abbr = away_abbr
                    # Tie: winner_abbr stays None
                except (TypeError, ValueError):
                    pass

            game_type = "regular" if season_type == 2 else "playoff"
            # ESPN external ID for deduplication
            external_id = event.get("id", "")

            return {
                "date": game_date,
                "season": season,
                "week": str(week),
                "game_type": game_type,
                "home_abbr": home_abbr,
                "away_abbr": away_abbr,
                "home_score": home_score,
                "away_score": away_score,
                "winner_abbr": winner_abbr,
                "overtime": status == "STATUS_FINAL_OT",
                "external_id": external_id,
            }
        except Exception as exc:
            logger.warning("Failed to parse ESPN event: %s", exc)
            return None

    def store_games(self, games: List[Dict[str, Any]]) -> tuple[int, int]:
        """
        Upsert parsed games into the DB `games` table.

        Returns:
            (inserted, skipped) counts.
        """
        if not self.db:
            raise RuntimeError("ScheduleScraper requires a db instance to store games")

        inserted = skipped = 0
        for g in games:
            home_team = self.db.get_team_by_abbreviation(g["home_abbr"])
            away_team = self.db.get_team_by_abbreviation(g["away_abbr"])
            if not home_team or not away_team:
                skipped += 1
                continue

            home_id = home_team["team_id"]
            away_id = away_team["team_id"]

            # Resolve winner_id
            winner_id: Optional[int] = None
            if g["winner_abbr"] == g["home_abbr"]:
                winner_id = home_id
            elif g["winner_abbr"] == g["away_abbr"]:
                winner_id = away_id

            # Check if game already exists (same home/away/date)
            existing = self.db.fetchone(
                """
                SELECT game_id, home_score FROM games
                WHERE home_team_id = ? AND away_team_id = ? AND date = ? AND season = ?
                """,
                (home_id, away_id, g["date"], g["season"]),
            )
            if existing:
                # Update score/winner if game is now completed and wasn't before
                if existing["home_score"] is None and g["home_score"] is not None:
                    self.db.execute(
                        """
                        UPDATE games
                        SET home_score=?, away_score=?, winner_id=?, overtime=?
                        WHERE game_id=?
                        """,
                        (g["home_score"], g["away_score"], winner_id,
                         1 if g["overtime"] else 0, existing["game_id"]),
                    )
                    self.db.commit()
                    inserted += 1
                else:
                    skipped += 1
                continue

            # Insert new game
            self.db.execute(
                """
                INSERT INTO games
                    (date, season, week, game_type, home_team_id, away_team_id,
                     home_score, away_score, winner_id, overtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    g["date"], g["season"], g["week"], g["game_type"],
                    home_id, away_id,
                    g["home_score"], g["away_score"],
                    winner_id,
                    1 if g["overtime"] else 0,
                ),
            )
            self.db.commit()
            inserted += 1

        return inserted, skipped
