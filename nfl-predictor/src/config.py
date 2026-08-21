"""Centralized configuration — single source of truth for env-driven settings.

All environment reads live here. Import `settings` everywhere instead of calling
`os.environ` directly, so the full configuration surface is discoverable in one file.

Env vars:
    ENV               "production" (default) or anything else for dev (enables reload)
    DB_PATH           Override SQLite path (default: <project>/data/nfl.db)
    ODDS_API_KEY      The Odds API key (optional; odds fetch skipped if empty)
    CORS_ORIGINS      Comma-separated allowed origins (default: localhost dev servers)
    PFR_RATE_LIMIT    Seconds between Pro-Football-Reference requests (default: 4.0)
"""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, Tuple

# nfl-predictor/  (src/config.py -> parent is src/, parent.parent is project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Season math ──────────────────────────────────────────────────────────────
# An NFL season runs Sep–early Feb and is named for the year it STARTS in, so
# the calendar year is never the season label on its own. These mirror
# frontend/src/config.ts; keep the two in step.

FIRST_SEASON = 1990


def current_nfl_season(today: Optional[date] = None) -> int:
    """The current NFL season label. Jan–Aug belongs to the previous label."""
    today = today or date.today()
    return today.year if today.month >= 9 else today.year - 1


def last_completed_season(today: Optional[date] = None) -> int:
    """Most recent season with a full set of played games.

    Not simply ``current_nfl_season() - 1``: from February to August the season
    labelled current has already finished, so it *is* the last completed one.
    """
    today = today or date.today()
    season = current_nfl_season(today)
    in_progress = today.month >= 9 or today.month == 1  # Sep–Dec + Jan playoffs
    return season - 1 if in_progress else season


def active_season(today: Optional[date] = None) -> int:
    """The season being drafted for or currently played.

    Deliberately ``last_completed + 1`` rather than ``current + 1``: the latter
    rolls to the following year the moment September arrives, even though the
    season just kicking off is the one fantasy actually cares about.
    """
    return last_completed_season(today) + 1


CURRENT_SEASON = current_nfl_season()
LAST_COMPLETED_SEASON = last_completed_season()
ACTIVE_SEASON = active_season()

_DEFAULT_CORS = (
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
)


def _csv_tuple(name: str, default: Tuple[str, ...]) -> Tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    env: str
    db_path: Path
    odds_api_key: str
    cors_origins: Tuple[str, ...]
    pfr_rate_limit: float

    @property
    def is_dev(self) -> bool:
        return self.env != "production"


def _load() -> Settings:
    db_path_env = os.environ.get("DB_PATH", "").strip()
    db_path = Path(db_path_env) if db_path_env else PROJECT_ROOT / "data" / "nfl.db"

    try:
        rate_limit = float(os.environ.get("PFR_RATE_LIMIT", "4.0"))
    except ValueError:
        rate_limit = 4.0

    return Settings(
        env=os.environ.get("ENV", "production"),
        db_path=db_path,
        odds_api_key=os.environ.get("ODDS_API_KEY", "").strip(),
        cors_origins=_csv_tuple("CORS_ORIGINS", _DEFAULT_CORS),
        pfr_rate_limit=rate_limit,
    )


settings = _load()
