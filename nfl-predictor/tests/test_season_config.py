"""Backend season constants must be date-derived, not literals.

The frontend already solved this (`frontend/src/config.ts`) after
LAST_COMPLETED_SEASON = CURRENT_SEASON - 1 served two-year-old stats through
the 2026 offseason. The API routers still carried hardcoded Query(2024)
defaults, which is the same bug one layer down.
"""

import re
from datetime import date
from pathlib import Path

import pytest

from src.config import (
    FIRST_SEASON,
    active_season,
    current_nfl_season,
    last_completed_season,
)


class TestCurrentNflSeason:
    """A season is named for the year it starts in, so Jan-Aug is last year."""

    @pytest.mark.parametrize(
        "today,expected",
        [
            (date(2026, 8, 21), 2025),  # August: 2025 season is the label
            (date(2026, 9, 1), 2026),  # September: 2026 season begins
            (date(2026, 12, 25), 2026),
            (date(2027, 1, 5), 2026),  # January playoffs still belong to 2026
            (date(2027, 2, 20), 2026),
        ],
    )
    def test_season_label(self, today, expected):
        assert current_nfl_season(today) == expected


class TestLastCompletedSeason:
    @pytest.mark.parametrize(
        "today,expected",
        [
            (date(2026, 2, 20), 2025),  # offseason: 2025 finished
            (date(2026, 8, 21), 2025),
            (date(2026, 9, 15), 2025),  # 2026 in progress, 2025 last complete
            (date(2026, 12, 25), 2025),
            (date(2027, 1, 5), 2025),  # January = playoffs of 2026
            (date(2027, 3, 1), 2026),
        ],
    )
    def test_last_completed(self, today, expected):
        assert last_completed_season(today) == expected

    def test_never_ahead_of_current(self):
        for month in range(1, 13):
            today = date(2026, month, 15)
            assert last_completed_season(today) <= current_nfl_season(today)


class TestActiveSeason:
    """The season fantasy is actually played/drafted for.

    Deliberately last_completed + 1 rather than the frontend's
    CURRENT_SEASON + 1, which jumps to 2027 the moment September 2026 arrives
    even though the 2026 season is the one being played.
    """

    @pytest.mark.parametrize(
        "today,expected",
        [
            (date(2026, 8, 21), 2026),  # drafting for 2026
            (date(2026, 10, 1), 2026),  # playing 2026
            (date(2027, 1, 5), 2026),  # still 2026
            (date(2027, 3, 1), 2027),
        ],
    )
    def test_active_season(self, today, expected):
        assert active_season(today) == expected

    def test_is_last_completed_plus_one(self):
        for month in range(1, 13):
            today = date(2026, month, 15)
            assert active_season(today) == last_completed_season(today) + 1


class TestNoHardcodedSeasonsInApi:
    """Guard against the literals creeping back.

    This is the test that stops the bug from rotting back in: routers used
    Query(2024) defaults long after 2024 stopped being relevant.
    """

    def test_no_year_literals_in_routers(self):
        api_dir = Path(__file__).resolve().parent.parent / "src" / "api"
        # Season *defaults* only — `ge=1960, le=2030` validation bounds are fine.
        pattern = re.compile(
            r"(Query\(\s*(19|20)\d\d|Field\(\s*(19|20)\d\d"
            r"|(season|year)\w*\s*:[^=]*=\s*(19|20)\d\d)"
        )
        offenders = []
        for path in api_dir.rglob("*.py"):
            for lineno, line in enumerate(path.read_text().splitlines(), start=1):
                if pattern.search(line) and "noqa: season" not in line:
                    offenders.append(f"{path.name}:{lineno}: {line.strip()}")
        assert offenders == [], "Hardcoded season literals found:\n" + "\n".join(
            offenders
        )


def test_first_season_unchanged():
    assert FIRST_SEASON == 1990
