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
from pathlib import Path
from typing import Tuple

# nfl-predictor/  (src/config.py -> parent is src/, parent.parent is project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

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
