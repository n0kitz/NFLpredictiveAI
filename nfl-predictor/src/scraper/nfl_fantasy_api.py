"""
EXPERIMENTAL read-only client for the unofficial fantasy.nfl.com API.

fantasy.nfl.com has no official public API. League-scoped endpoints require
an authenticated session cookie, supplied via the NFL_FANTASY_COOKIE env var
(copy the Cookie header from a logged-in browser session). The endpoint
shapes are reverse-engineered and may break without notice — every consumer
must degrade gracefully to the manual import path.

Only league settings and rosters are read; nothing is ever written.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from .http import get_with_retry

logger = logging.getLogger(__name__)

LEAGUE_URL = "https://api.fantasy.nfl.com/v3/leagues/{league_id}"


def _first_league(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    leagues = data.get("leagues") or []
    return leagues[0] if leagues else None


def parse_league_settings(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract league id/name/size/scoring from a league API payload."""
    league = _first_league(data)
    if not league:
        return None
    size = league.get("size") or 10
    size = max(8, min(20, int(size)))

    reception_pts = float(
        (league.get("scoringSettings") or {}).get("receptionPoints") or 0
    )
    if reception_pts >= 1:
        scoring = "ppr"
    elif reception_pts > 0:
        scoring = "half_ppr"
    else:
        scoring = "standard"

    return {
        "league_id": str(league.get("id", "")),
        "name": league.get("name", ""),
        "league_size": size,
        "scoring": scoring,
    }


def parse_league_rosters(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract per-team rosters as [(player_name, position)] lists."""
    league = _first_league(data)
    if not league:
        return []
    teams: List[Dict[str, Any]] = []
    for team in league.get("teams") or []:
        players: List[Tuple[str, str]] = []
        roster = team.get("roster") or {}
        for p in roster.get("players") or []:
            name = (p.get("name") or "").strip()
            if name:
                players.append((name, (p.get("position") or "").strip()))
        teams.append(
            {
                "team_id": str(team.get("id", "")),
                "team_name": team.get("name", ""),
                "players": players,
            }
        )
    return teams


def fetch_league(league_id: str) -> Optional[Dict[str, Any]]:
    """Fetch raw league JSON. Returns None on any failure (no cookie, HTTP
    error, shape change) — callers fall back to manual import."""
    cookie = os.environ.get("NFL_FANTASY_COOKIE", "").strip()
    if not cookie:
        logger.info("NFL_FANTASY_COOKIE not set — NFL.com sync unavailable")
        return None
    try:
        resp = get_with_retry(
            LEAGUE_URL.format(league_id=league_id),
            headers={
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
            timeout=15,
        )
        if resp is None or resp.status_code != 200:
            logger.warning(
                "NFL.com league fetch failed (status %s)",
                getattr(resp, "status_code", "n/a"),
            )
            return None
        return resp.json()
    except Exception as exc:
        logger.warning("NFL.com league fetch failed: %s", exc)
        return None
