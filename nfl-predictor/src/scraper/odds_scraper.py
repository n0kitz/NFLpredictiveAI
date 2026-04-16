"""Fetch NFL betting odds from The Odds API (https://the-odds-api.com)."""

import logging
import os
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# The Odds API full team name → our internal abbreviation
TEAM_NAME_MAP: dict[str, str] = {
    "Arizona Cardinals":    "ARI",
    "Atlanta Falcons":      "ATL",
    "Baltimore Ravens":     "BAL",
    "Buffalo Bills":        "BUF",
    "Carolina Panthers":    "CAR",
    "Chicago Bears":        "CHI",
    "Cincinnati Bengals":   "CIN",
    "Cleveland Browns":     "CLE",
    "Dallas Cowboys":       "DAL",
    "Denver Broncos":       "DEN",
    "Detroit Lions":        "DET",
    "Green Bay Packers":    "GB",
    "Houston Texans":       "HOU",
    "Indianapolis Colts":   "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs":   "KC",
    "Las Vegas Raiders":    "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams":     "LAR",
    "Miami Dolphins":       "MIA",
    "Minnesota Vikings":    "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints":   "NO",
    "New York Giants":      "NYG",
    "New York Jets":        "NYJ",
    "Philadelphia Eagles":  "PHI",
    "Pittsburgh Steelers":  "PIT",
    "San Francisco 49ers":  "SF",
    "Seattle Seahawks":     "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans":     "TEN",
    "Washington Commanders":"WAS",
    # Historical / alternate names that may appear
    "Washington Football Team": "WAS",
    "Washington Redskins":      "WAS",
    "Oakland Raiders":          "OAK",
    "San Diego Chargers":       "SD",
    "St. Louis Rams":           "STL",
}

_BASE = "https://api.the-odds-api.com/v4"


class OddsScraper:
    """
    Fetches NFL betting odds from The Odds API.

    API key is read from the ODDS_API_KEY environment variable (or passed
    explicitly).  If the key is absent all methods log a warning and return
    empty lists so the rest of the application keeps working.
    """

    def __init__(self) -> None:
        self.last_requests_remaining: Optional[int] = None
        self.last_requests_used: Optional[int] = None

    # ── Static helpers ──────────────────────────────────────────────────────

    @staticmethod
    def american_odds_to_implied_prob(odds: int) -> float:
        """Convert American odds integer to raw implied probability (0–1)."""
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        return 100 / (odds + 100)

    @staticmethod
    def map_team_name(full_name: str) -> str:
        """Map The Odds API full team name to our internal abbreviation."""
        return TEAM_NAME_MAP.get(full_name, full_name)

    # ── API calls ───────────────────────────────────────────────────────────

    def fetch_upcoming_odds(self, api_key: str) -> list[dict]:
        """
        Fetch upcoming NFL game odds (spreads, totals, moneyline h2h).

        Returns a list of dicts, one per game, with keys:
            external_game_id, home_team (abbr), away_team (abbr), game_date,
            spread (home perspective, negative = home favoured), over_under,
            home_implied_prob, away_implied_prob, fetched_at (ISO UTC)

        The implied probabilities are vig-adjusted (sum to exactly 1.0).
        Returns [] if the request fails or the key is empty.
        """
        if not api_key:
            logger.warning("ODDS_API_KEY is empty — skipping upcoming odds fetch")
            return []

        try:
            resp = requests.get(
                f"{_BASE}/sports/americanfootball_nfl/odds",
                params={
                    "apiKey":      api_key,
                    "regions":     "us",
                    "markets":     "spreads,totals,h2h",
                    "oddsFormat":  "american",
                },
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Failed to fetch upcoming odds: %s", exc)
            return []

        # Capture rate-limit headers for the caller to inspect
        self.last_requests_remaining = _safe_int(
            resp.headers.get("x-requests-remaining")
        )
        self.last_requests_used = _safe_int(
            resp.headers.get("x-requests-used")
        )

        fetched_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        results: list[dict] = []

        for game in resp.json():
            home_name = game.get("home_team", "")
            away_name = game.get("away_team", "")
            commence  = game.get("commence_time", "")
            game_date = commence[:10] if commence else ""  # YYYY-MM-DD

            spread       = None
            over_under   = None
            home_ml: Optional[int] = None
            away_ml: Optional[int] = None

            for bookmaker in game.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    key      = market["key"]
                    outcomes = {o["name"]: o for o in market.get("outcomes", [])}

                    if key == "spreads" and spread is None:
                        h = outcomes.get(home_name)
                        if h:
                            spread = h.get("point")

                    elif key == "totals" and over_under is None:
                        ov = outcomes.get("Over")
                        if ov:
                            over_under = ov.get("point")

                    elif key == "h2h" and home_ml is None:
                        h = outcomes.get(home_name)
                        a = outcomes.get(away_name)
                        if h and a:
                            home_ml = int(h["price"])
                            away_ml = int(a["price"])

                # Stop after first bookmaker that has all three markets
                if home_ml is not None and spread is not None and over_under is not None:
                    break

            # Vig-adjusted implied probs
            home_implied = away_implied = None
            if home_ml is not None and away_ml is not None:
                h_raw = self.american_odds_to_implied_prob(home_ml)
                a_raw = self.american_odds_to_implied_prob(away_ml)
                total = h_raw + a_raw
                home_implied = round(h_raw / total, 4)
                away_implied = round(a_raw / total, 4)

            results.append({
                "external_game_id":  game.get("id", ""),
                "home_team":         self.map_team_name(home_name),
                "away_team":         self.map_team_name(away_name),
                "game_date":         game_date,
                "spread":            spread,
                "over_under":        over_under,
                "home_implied_prob": home_implied,
                "away_implied_prob": away_implied,
                "fetched_at":        fetched_at,
            })

        return results

    def fetch_historical_odds(self, api_key: str, season: int) -> list[dict]:
        """
        Fetch historical odds / scores for a season.

        Note: the historical endpoint requires a paid API tier.
        Returns [] silently on 401/403 (free-tier key).
        """
        if not api_key:
            logger.warning("ODDS_API_KEY is empty — skipping historical odds fetch")
            return []

        try:
            resp = requests.get(
                f"{_BASE}/sports/americanfootball_nfl/scores",
                params={
                    "apiKey":   api_key,
                    "daysFrom": 3,
                    "season":   season,
                },
                timeout=10,
            )
            if resp.status_code in (401, 403):
                logger.warning(
                    "Historical odds unavailable (HTTP %d) — paid API tier required",
                    resp.status_code,
                )
                return []
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Failed to fetch historical odds: %s", exc)
            return []

        return resp.json()


# ── Private helpers ─────────────────────────────────────────────────────────

def _safe_int(value: Optional[str]) -> Optional[int]:
    """Convert a header string to int, None if missing/invalid."""
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None
