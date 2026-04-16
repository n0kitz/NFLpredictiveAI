"""Fetch NFL injury reports from ESPN's public API (no auth required)."""

import logging
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# (latitude, longitude, is_dome) for each team's 2024 home stadium.
# Dome/retractable-roof venues return weather="Dome" immediately.
STADIUM_COORDS: dict[str, tuple[float, float, bool]] = {
    "ARI": (33.5276, -112.2626, True),   # State Farm Stadium (retractable)
    "ATL": (33.7554,  -84.4008, True),   # Mercedes-Benz Stadium (fixed dome)
    "BAL": (39.2780,  -76.6228, False),  # M&T Bank Stadium
    "BUF": (42.7738,  -78.7870, False),  # Highmark Stadium
    "CAR": (35.2258,  -80.8528, False),  # Bank of America Stadium
    "CHI": (41.8623,  -87.6167, False),  # Soldier Field
    "CIN": (39.0954,  -84.5160, False),  # Paycor Stadium
    "CLE": (41.5061,  -81.6995, False),  # Cleveland Browns Stadium
    "DAL": (32.7479,  -97.0929, True),   # AT&T Stadium (retractable)
    "DEN": (39.7440, -105.0202, False),  # Empower Field at Mile High
    "DET": (42.3400,  -83.0456, True),   # Ford Field (fixed dome)
    "GB":  (44.5013,  -88.0622, False),  # Lambeau Field
    "HOU": (29.6847,  -95.4107, True),   # NRG Stadium (retractable)
    "IND": (39.7601,  -86.1639, True),   # Lucas Oil Stadium (retractable)
    "JAX": (30.3240,  -81.6373, False),  # EverBank Stadium
    "KC":  (39.0489,  -94.4839, False),  # GEHA Field at Arrowhead
    "LAC": (33.9535, -118.3392, True),   # SoFi Stadium (retractable)
    "LAR": (33.9535, -118.3392, True),   # SoFi Stadium (retractable)
    "LV":  (36.0909, -115.1833, True),   # Allegiant Stadium (fixed dome)
    "MIA": (25.9580,  -80.2389, False),  # Hard Rock Stadium
    "MIN": (44.9736,  -93.2575, True),   # U.S. Bank Stadium (fixed dome)
    "NE":  (42.0909,  -71.2643, False),  # Gillette Stadium
    "NO":  (29.9511,  -90.0812, True),   # Caesars Superdome (fixed dome)
    "NYG": (40.8135,  -74.0745, False),  # MetLife Stadium
    "NYJ": (40.8135,  -74.0745, False),  # MetLife Stadium
    "PHI": (39.9008,  -75.1675, False),  # Lincoln Financial Field
    "PIT": (40.4468,  -80.0158, False),  # Acrisure Stadium
    "SEA": (47.5952, -122.3316, False),  # Lumen Field
    "SF":  (37.4035, -121.9694, False),  # Levi's Stadium
    "TB":  (27.9759,  -82.5033, False),  # Raymond James Stadium
    "TEN": (36.1665,  -86.7713, False),  # Nissan Stadium
    "WAS": (38.9077,  -76.8645, False),  # Northwest Stadium (FedEx Field)
}

# ESPN team abbreviation → internal abbreviation
ESPN_TEAM_MAP: dict[str, str] = {
    "ARI": "ARI",
    "ATL": "ATL",
    "BAL": "BAL",
    "BUF": "BUF",
    "CAR": "CAR",
    "CHI": "CHI",
    "CIN": "CIN",
    "CLE": "CLE",
    "DAL": "DAL",
    "DEN": "DEN",
    "DET": "DET",
    "GB":  "GB",
    "HOU": "HOU",
    "IND": "IND",
    "JAC": "JAX",   # ESPN uses JAC; internal is JAX
    "KC":  "KC",
    "LA":  "LAR",   # ESPN uses LA for the Rams; internal is LAR
    "LAC": "LAC",
    "LV":  "LV",
    "MIA": "MIA",
    "MIN": "MIN",
    "NE":  "NE",
    "NO":  "NO",
    "NYG": "NYG",
    "NYJ": "NYJ",
    "PHI": "PHI",
    "PIT": "PIT",
    "SEA": "SEA",
    "SF":  "SF",
    "TB":  "TB",
    "TEN": "TEN",
    "WSH": "WAS",   # ESPN uses WSH; internal is WAS
}

_ESPN_INJURIES_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
)


class InjuryScraper:
    """Scrape NFL injury reports from ESPN's public API."""

    KEY_POSITIONS: list[str] = ["QB", "WR", "RB", "TE", "OT", "CB", "DE", "LB"]

    # Statuses treated as meaningfully impactful
    _SIGNIFICANT_STATUSES: frozenset[str] = frozenset(
        ["Out", "Doubtful", "IR", "PUP"]
    )

    def fetch_injuries(self) -> list[dict]:
        """
        GET ESPN injuries endpoint and return a flat list of dicts.

        Each dict has: team_abbr, player_name, position, injury_status,
        report_date (today ISO string).
        Returns [] on any network error.
        """
        try:
            resp = requests.get(_ESPN_INJURIES_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("Failed to fetch ESPN injuries: %s", exc)
            return []
        except Exception as exc:
            logger.warning("Unexpected error fetching injuries: %s", exc)
            return []

        today = datetime.utcnow().strftime("%Y-%m-%d")
        results: list[dict] = []

        # ESPN returns either data["injuries"] or data["items"]
        entries = data.get("injuries", data.get("items", []))

        for entry in entries:
            team = entry.get("team", {})
            espn_abbr = team.get("abbreviation", "")
            internal_abbr = ESPN_TEAM_MAP.get(espn_abbr, espn_abbr)

            for inj in entry.get("injuries", []):
                athlete = inj.get("athlete", {})
                pos_obj = athlete.get("position", {})
                position = pos_obj.get("abbreviation", "") if isinstance(pos_obj, dict) else ""

                # Status lives in different fields depending on API version
                status = (
                    inj.get("status")
                    or inj.get("type", {}).get("description", "")
                    or inj.get("type", {}).get("name", "")
                )

                results.append({
                    "team_abbr":      internal_abbr,
                    "player_name":    athlete.get("displayName", ""),
                    "position":       position,
                    "injury_status":  str(status).strip(),
                    "report_date":    today,
                })

        return results

    def filter_key_players(self, injuries: list[dict]) -> list[dict]:
        """
        Return only injuries for key positions with significant impact status.

        Keeps: position in KEY_POSITIONS AND status in {Out, Doubtful, IR, PUP}.
        """
        return [
            inj for inj in injuries
            if inj.get("position") in self.KEY_POSITIONS
            and inj.get("injury_status") in self._SIGNIFICANT_STATUSES
        ]
