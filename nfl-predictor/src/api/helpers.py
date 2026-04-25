"""Shared helper utilities for API route handlers."""

from typing import Optional, List
from fastapi import HTTPException

from .schemas import (
    GameResponse, InjuryEntry, WeatherResponse,
    PlayerEntry, PlayerStatsEntry,
)


def resolve_team(db, identifier: str):
    """Look up a team by identifier, raise 404 if not found."""
    team = db.find_team(identifier)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team not found: {identifier}")
    return team


def build_weather_response(w_row) -> WeatherResponse:
    """Convert a DB weather row to a WeatherResponse."""
    w = dict(w_row)
    return WeatherResponse(
        is_dome=bool(w.get("is_dome", 0)),
        condition=w.get("condition", "Unknown"),
        temperature_c=w.get("temperature_c"),
        wind_speed_kmh=w.get("wind_speed_kmh"),
        precipitation_mm=w.get("precipitation_mm"),
        weather_code=w.get("weather_code"),
        is_adverse=bool(w.get("is_adverse", 0)),
    )


def build_injury_list(rows) -> List[InjuryEntry]:
    """Convert DB injury rows to a list of InjuryEntry."""
    return [
        InjuryEntry(
            player_name=r["player_name"],
            position=r["position"],
            injury_status=r["injury_status"],
            report_date=r["report_date"],
        )
        for r in rows
    ]


def row_to_game(row) -> GameResponse:
    """Convert a database row to GameResponse."""
    d = dict(row)
    return GameResponse(
        game_id=d.get("game_id", 0),
        date=str(d.get("date", "")),
        season=d.get("season", 0),
        week=str(d.get("week", "")),
        game_type=d.get("game_type", "regular"),
        home_team_id=d.get("home_team_id", 0),
        away_team_id=d.get("away_team_id", 0),
        home_team=d.get("home_team"),
        home_abbr=d.get("home_abbr"),
        away_team=d.get("away_team"),
        away_abbr=d.get("away_abbr"),
        home_score=d.get("home_score"),
        away_score=d.get("away_score"),
        winner=d.get("winner"),
        winner_abbr=d.get("winner_abbr"),
        winner_id=d.get("winner_id"),
        overtime=bool(d.get("overtime", False)),
    )


def row_to_player_entry(row) -> PlayerEntry:
    """Convert a roster DB row to a PlayerEntry."""
    d = dict(row)
    stats = None
    if d.get("games_played") is not None:
        stats = PlayerStatsEntry(
            games_played=d.get("games_played", 0),
            pass_attempts=d.get("pass_attempts", 0),
            pass_completions=d.get("pass_completions", 0),
            pass_yards=d.get("pass_yards", 0),
            pass_tds=d.get("pass_tds", 0),
            interceptions=d.get("interceptions", 0),
            passer_rating=d.get("passer_rating", 0.0),
            rush_attempts=d.get("rush_attempts", 0),
            rush_yards=d.get("rush_yards", 0),
            rush_tds=d.get("rush_tds", 0),
            yards_per_carry=d.get("yards_per_carry", 0.0),
            targets=d.get("targets", 0),
            receptions=d.get("receptions", 0),
            rec_yards=d.get("rec_yards", 0),
            rec_tds=d.get("rec_tds", 0),
            yards_per_reception=d.get("yards_per_reception", 0.0),
            fantasy_points_ppr=d.get("fantasy_points_ppr", 0.0),
            fantasy_points_standard=d.get("fantasy_points_standard", 0.0),
        )
    return PlayerEntry(
        player_id=d["player_id"],
        espn_id=d.get("espn_id"),
        full_name=d.get("full_name", ""),
        position=d.get("position"),
        jersey_number=d.get("jersey_number"),
        depth_position=d.get("depth_position"),
        is_starter=bool(d.get("is_starter", 0)),
        roster_status=d.get("roster_status"),
        height_cm=d.get("height_cm"),
        weight_kg=d.get("weight_kg"),
        college=d.get("college"),
        experience_years=d.get("experience_years", 0),
        headshot_url=d.get("headshot_url"),
        stats=stats,
    )
