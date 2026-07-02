"""EXPERIMENTAL: fantasy.nfl.com league sync (read-only, cookie-gated).

Returns the league's settings and rosters so the frontend can apply them to
LeagueSettings + the roster importer. Requires NFL_FANTASY_COOKIE server-side;
without it (or on any upstream failure) responds 503 and the UI falls back to
manual import.
"""

import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["nfl-league"])


@router.get("/api/nfl-league/{league_id}")
def get_nfl_league(league_id: str):
    from ...scraper.nfl_fantasy_api import (
        fetch_league, parse_league_settings, parse_league_rosters,
    )

    data = fetch_league(league_id)
    if data is None:
        raise HTTPException(
            status_code=503,
            detail="NFL.com sync unavailable (cookie missing, expired, or the "
                   "unofficial API changed). Use manual roster import instead.",
        )
    settings = parse_league_settings(data)
    if settings is None:
        raise HTTPException(status_code=404, detail="League not found in response")
    return {
        'settings': settings,
        'teams': parse_league_rosters(data),
        'experimental': True,
    }
