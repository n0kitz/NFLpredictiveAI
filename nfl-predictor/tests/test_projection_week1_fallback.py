"""Week-1 projections must differentiate players, not emit position constants.

Two defects, one visible symptom. The cached 2026 wk1 board had four QBs at
exactly 12.04 and four more at 7.72, with backups on top:

1. ``build_player_feature_vector`` reads history only from *within* the
   requested season, so at week 1 every rolling/usage feature is 0.0 — for a
   played season too, not just a future one (verified: Bijan 2025 wk1 rolling
   averages are all 0.0, 2025 wk10 are 20.1/21.1). The ML model therefore
   cannot tell an elite RB from a backup and returns a position-level
   constant. Fix: skip the ML override when the player has no in-season
   history and let the heuristic answer instead — which is what
   ``calculate_projection`` (the verified single-player path) already does.

2. The heuristic base itself came from a LEFT JOIN pinned to the exact
   season, and ``player_season_stats`` has no rows for an unplayed season, so
   the fallback path was *also* zeroed. Fix: join the most recent season
   at-or-before the requested one, mirroring ``get_player_stats``' fallback
   while staying leak-free.
"""

import pytest

from src.database.db import Database
from src.prediction.fantasy_scorer import FantasyScorer


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "wk1.db")
    for tid, name, abbr, city in [
        (1, "Falcons", "ATL", "Atlanta"),
        (2, "Saints", "NO", "New Orleans"),
    ]:
        database.execute(
            "INSERT INTO teams (team_id, name, abbreviation, city, conference, division) "
            "VALUES (?, ?, ?, ?, 'NFC', 'NFC South')",
            (tid, name, abbr, city),
        )
    # An elite RB and a backup QB — the exact inversion seen on the live board.
    database.execute(
        "INSERT INTO players (player_id, full_name, position) VALUES (10, 'Elite Back', 'RB')"
    )
    database.execute(
        "INSERT INTO players (player_id, full_name, position) VALUES (11, 'Backup Passer', 'QB')"
    )
    for pid, team in ((10, 1), (11, 2)):
        database.execute(
            "INSERT INTO roster_entries (player_id, team_id, season, is_starter) "
            "VALUES (?, ?, 2026, 1)",
            (pid, team),
        )
    # 2025 season totals exist; 2026 (the season being projected) has none.
    database.execute("""INSERT INTO player_season_stats
           (player_id, team_id, season, games_played, fantasy_points_ppr,
            fantasy_points_standard, targets)
           VALUES (10, 1, 2025, 17, 306.0, 289.0, 80)""")
    database.execute("""INSERT INTO player_season_stats
           (player_id, team_id, season, games_played, fantasy_points_ppr,
            fantasy_points_standard, targets)
           VALUES (11, 2, 2025, 17, 51.0, 51.0, 0)""")
    database.execute(
        "INSERT INTO games (game_id, date, season, week, game_type, home_team_id, away_team_id) "
        "VALUES (500, '2026-09-10', 2026, '1', 'regular', 1, 2)"
    )
    yield database
    database.close()


def _by_name(results):
    return {r["full_name"]: r for r in results}


class TestSeasonFallback:
    def test_prior_season_stats_drive_the_base(self, db):
        """No 2026 season stats exist, so the 2025 per-game average must be used."""
        results = FantasyScorer(db).generate_weekly_projections(2026, 1)
        rb = _by_name(results)["Elite Back"]
        # 289.0 standard / 17 games = 17.0 per game, before matchup scaling.
        assert rb["projected_points_std"] > 5.0, (
            "elite RB projected at ~0 — the season join is still pinned to an "
            "empty season instead of falling back"
        )

    def test_elite_rb_outprojects_backup_qb(self, db):
        """The live inversion: backups sat on top of the board at 12.04."""
        results = _by_name(FantasyScorer(db).generate_weekly_projections(2026, 1))
        assert (
            results["Elite Back"]["projected_points_std"]
            > results["Backup Passer"]["projected_points_std"]
        )

    def test_no_future_leakage(self, db):
        """A 2027 stat line must never feed a 2026 projection."""
        db.execute("""INSERT INTO player_season_stats
               (player_id, team_id, season, games_played, fantasy_points_ppr,
                fantasy_points_standard, targets)
               VALUES (10, 1, 2027, 17, 9999.0, 9999.0, 300)""")
        results = _by_name(FantasyScorer(db).generate_weekly_projections(2026, 1))
        assert results["Elite Back"]["projected_points_std"] < 100.0


class TestMlSkippedWithoutHistory:
    def test_week1_uses_heuristic_not_ml(self, db):
        """With no in-season history the ML vector is degenerate — don't use it."""
        results = _by_name(FantasyScorer(db).generate_weekly_projections(2026, 1))
        assert results["Elite Back"]["model_source"] == "heuristic"
        assert results["Backup Passer"]["model_source"] == "heuristic"

    def test_players_are_differentiated(self, db):
        """The symptom: identical constants across unrelated players."""
        results = FantasyScorer(db).generate_weekly_projections(2026, 1)
        points = [r["projected_points_std"] for r in results]
        assert len(set(points)) > 1, f"all players share one value: {points}"

    def test_midseason_with_history_still_uses_ml(self, db):
        """Guard against over-correcting: ML must still drive weeks that have data."""
        from src.prediction.player_ml_model import get_cache

        if get_cache().get_model("RB") is None:
            pytest.skip("no trained RB model artifact available")
        for wk in range(1, 5):
            db.execute(
                """INSERT INTO player_weekly_stats
                   (player_id, season, week, team_id, position, snaps,
                    rush_yards, rush_tds, rec_yards, fantasy_points_ppr,
                    fantasy_points_standard)
                   VALUES (10, 2026, ?, 1, 'RB', 40, 90, 1, 20, 20.0, 19.0)""",
                (wk,),
            )
        db.execute(
            "INSERT INTO games (game_id, date, season, week, game_type, home_team_id, away_team_id) "
            "VALUES (505, '2026-10-12', 2026, '5', 'regular', 1, 2)"
        )
        results = _by_name(FantasyScorer(db).generate_weekly_projections(2026, 5))
        assert results["Elite Back"]["model_source"] == "ml"
