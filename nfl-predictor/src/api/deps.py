"""Dependency injection for FastAPI endpoints."""

from typing import Generator
from ..database.db import Database, create_database, DEFAULT_DB_PATH


def get_db() -> Generator[Database, None, None]:
    """
    FastAPI dependency that provides a Database instance per request.
    Automatically closes the connection when the request finishes.
    """
    db = create_database(DEFAULT_DB_PATH)
    try:
        yield db
    finally:
        db.close()


# ── PredictionEngine singleton ─────────────────────────
# Loaded once at startup; shared across all routers.
from ..prediction.engine import PredictionEngine  # noqa: E402

_prediction_engine: PredictionEngine | None = None


def get_engine() -> PredictionEngine:
    global _prediction_engine
    if _prediction_engine is None:
        _prediction_engine = PredictionEngine(Database(DEFAULT_DB_PATH))
    return _prediction_engine
