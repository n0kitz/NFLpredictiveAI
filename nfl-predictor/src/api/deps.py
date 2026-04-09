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
