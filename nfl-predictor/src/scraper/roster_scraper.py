"""
Roster scraper using the ESPN public site API (no auth required).

Fetches current NFL roster data for all 32 teams.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple

import requests

from .http import get_with_retry

logger = logging.getLogger(__name__)

# ESPN team ID → internal abbreviation mapping (all 32 current teams)
ESPN_TEAM_IDS: Dict[str, int] = {
    "ARI": 22,
    "ATL": 1,
    "BAL": 33,
    "BUF": 2,
    "CAR": 29,
    "CHI": 3,
    "CIN": 4,
    "CLE": 5,
    "DAL": 6,
    "DEN": 7,
    "DET": 8,
    "GB": 9,
    "HOU": 34,
    "IND": 11,
    "JAX": 30,
    "KC": 12,
    "LAC": 24,
    "LAR": 14,
    "LV": 13,
    "MIA": 15,
    "MIN": 16,
    "NE": 17,
    "NO": 18,
    "NYG": 19,
    "NYJ": 20,
    "PHI": 21,
    "PIT": 23,
    "SEA": 26,
    "SF": 25,
    "TB": 27,
    "TEN": 10,
    "WAS": 28,
}

ESPN_ROSTER_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
    "/teams/{espn_id}/roster"
)
ESPN_PLAYER_STATS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
    "/athletes/{espn_id}/stats?season={season}"
)

# ESPN's site API 403s custom and browser-spoofed User-Agents (verified
# 2026-08-20: every one of the 32 team endpoints returned 403). It still serves
# honest client identifiers, so we deliberately leave the default
# ``python-requests/x.y.z`` UA in place instead of setting our own.
# Guarded by tests/test_espn_user_agent.py.


def evaluate_roster_import(
    teams_fetched: int,
    entries_upserted: int,
    expected_teams: int = 32,
) -> Tuple[bool, str]:
    """Judge the outcome of a roster-import run.

    A run that upserts nothing is a hard failure even though no exception was
    raised — that is exactly what the 2026-08-20 ESPN 403 outage looked like,
    and it was reported as success. Callers should exit non-zero when ``ok`` is
    False so cron and humans notice.

    Args:
        teams_fetched:    Teams that returned at least one player.
        entries_upserted: Roster entries written to the DB.
        expected_teams:   Teams the run should have covered (32 in the NFL).

    Returns:
        ``(ok, message)`` — ``message`` is always non-empty and safe to print.
    """
    coverage = f"{teams_fetched}/{expected_teams}"

    if entries_upserted == 0:
        return False, (
            f"FAILED: no roster entries upserted ({coverage} teams returned "
            "players). Every ESPN fetch failed — check for a 403 (User-Agent "
            "policy) or an upstream outage before trusting the draft board."
        )

    if teams_fetched < expected_teams:
        return True, (
            f"PARTIAL: only {coverage} teams returned players "
            f"({entries_upserted} entries). Missing teams keep stale roster data."
        )

    return True, f"OK: {coverage} teams imported ({entries_upserted} entries)."


def _inches_to_cm(inches: Optional[int]) -> Optional[float]:
    if inches is None:
        return None
    return round(float(inches) * 2.54, 1)


def _lbs_to_kg(lbs: Optional[int]) -> Optional[float]:
    if lbs is None:
        return None
    return round(float(lbs) * 0.453592, 1)


class RosterScraper:
    """Fetch NFL roster data from the ESPN public site API."""

    def __init__(self, request_delay: float = 1.0):
        self._delay = request_delay
        self._session = requests.Session()

    def fetch_team_roster(self, team_abbr: str) -> List[Dict[str, Any]]:
        """
        Fetch current roster for one team from ESPN.

        Args:
            team_abbr: Internal team abbreviation (e.g. "KC", "NE").

        Returns:
            List of player dicts. Empty list on any error.
        """
        espn_id = ESPN_TEAM_IDS.get(team_abbr.upper())
        if espn_id is None:
            logger.warning("No ESPN team ID for abbreviation: %s", team_abbr)
            return []

        url = ESPN_ROSTER_URL.format(espn_id=espn_id)
        try:
            resp = get_with_retry(url, timeout=15, session=self._session)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Failed to fetch roster for %s: %s", team_abbr, exc)
            return []

        players: List[Dict[str, Any]] = []
        # ESPN roster response groups athletes by position group
        for group in data.get("athletes", []):
            for athlete in group.get("items", []):
                players.append(self._parse_athlete(athlete))

        logger.debug("  %s: %d players fetched", team_abbr, len(players))
        return players

    def fetch_all_rosters(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch current rosters for all 32 NFL teams.

        Returns dict mapping team_abbr → list of player dicts.
        """
        result: Dict[str, List[Dict[str, Any]]] = {}
        for abbr in ESPN_TEAM_IDS:
            logger.info("Fetching roster: %s", abbr)
            result[abbr] = self.fetch_team_roster(abbr)
            time.sleep(self._delay)
        return result

    def fetch_player_stats_espn(
        self, espn_id: str, season: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch per-season stats for a player from ESPN athlete stats endpoint.

        Returns parsed stats dict or None on error.
        """
        url = ESPN_PLAYER_STATS_URL.format(espn_id=espn_id, season=season)
        try:
            resp = get_with_retry(url, timeout=15, session=self._session)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_athlete_stats(data)
        except Exception as exc:
            logger.debug(
                "Could not fetch stats for espn_id=%s season=%s: %s",
                espn_id,
                season,
                exc,
            )
            return None

    # ── Private helpers ──────────────────────────────────────────────────────

    def _parse_athlete(self, athlete: Dict[str, Any]) -> Dict[str, Any]:
        """Extract player fields from an ESPN athlete object."""
        # ESPN player IDs are numeric strings
        espn_id = str(athlete.get("id", ""))
        full_name = athlete.get("displayName") or athlete.get("fullName") or ""
        first_name = athlete.get("firstName", "")
        last_name = athlete.get("lastName", "")

        # Position (ESPN uses "PK" for placekickers; normalize to "K" so
        # fantasy position filters match)
        pos = athlete.get("position", {})
        position = pos.get("abbreviation") if isinstance(pos, dict) else None
        if position == "PK":
            position = "K"

        # Jersey
        jersey = athlete.get("jersey")

        # Physical measurements (ESPN provides inches for height, lbs for weight)
        height_in = athlete.get("height")  # inches (int or None)
        weight_lb = athlete.get("weight")  # lbs (int or None)

        # Date of birth (ISO string)
        dob = athlete.get("dateOfBirth")  # e.g. "1995-09-17T00:00Z"
        if dob:
            dob = str(dob)[:10]  # keep only YYYY-MM-DD

        # College
        college_obj = athlete.get("college") or {}
        college = college_obj.get("name") if isinstance(college_obj, dict) else None

        # Experience
        exp_obj = athlete.get("experience") or {}
        exp_years = exp_obj.get("years", 0) if isinstance(exp_obj, dict) else 0

        # Status
        status_obj = athlete.get("status") or {}
        status = (
            status_obj.get("name", "Active")
            if isinstance(status_obj, dict)
            else "Active"
        )

        # Headshot
        headshot_obj = athlete.get("headshot") or {}
        headshot_url = (
            headshot_obj.get("href") if isinstance(headshot_obj, dict) else None
        )

        return {
            "espn_id": espn_id,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "position": position,
            "jersey_number": str(jersey) if jersey is not None else None,
            "date_of_birth": dob,
            "height_cm": _inches_to_cm(height_in),
            "weight_kg": _lbs_to_kg(weight_lb),
            "college": college,
            "experience_years": int(exp_years) if exp_years else 0,
            "status": status,
            "headshot_url": headshot_url,
        }

    def _parse_athlete_stats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse ESPN athlete stats response into a flat dict."""
        stats_out: Dict[str, Any] = {}
        for category in data.get("statistics", []):
            labels = category.get("labels", [])
            values = category.get("values", [])
            for label, val in zip(labels, values):
                try:
                    stats_out[label] = float(val)
                except (TypeError, ValueError):
                    stats_out[label] = val
        return stats_out
