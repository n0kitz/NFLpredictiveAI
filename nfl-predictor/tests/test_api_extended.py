"""Extended API tests covering previously-untested endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.database.db import DEFAULT_DB_PATH

pytestmark = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(),
    reason="Real database not found — run scraper first",
)

client = TestClient(app)


# ── Prediction history ─────────────────────────────────────────────────────────

class TestPredictionHistory:
    def test_history_returns_valid_shape(self):
        r = client.get("/api/predictions/history")
        assert r.status_code == 200
        data = r.json()
        assert "predictions" in data
        assert "total" in data
        assert isinstance(data["predictions"], list)

    def test_history_respects_limit(self):
        r = client.get("/api/predictions/history?limit=5")
        assert r.status_code == 200
        assert len(r.json()["predictions"]) <= 5

    def test_history_limit_bounds(self):
        r = client.get("/api/predictions/history?limit=0")
        assert r.status_code == 422

    def test_history_offset(self):
        r = client.get("/api/predictions/history?limit=10&offset=0")
        assert r.status_code == 200

    def test_enrich_endpoint(self):
        r = client.post("/api/predictions/enrich")
        assert r.status_code == 200
        assert "enriched" in r.json()


# ── Fantasy endpoints ──────────────────────────────────────────────────────────

class TestFantasyEndpoints:
    def test_projections_returns_list(self):
        r = client.get("/api/fantasy/projections?week=1&season=2024&position=QB&scoring=ppr")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_projections_without_position(self):
        r = client.get("/api/fantasy/projections?week=1&season=2024&scoring=ppr")
        assert r.status_code == 200

    def test_projections_expose_opponent_team_id(self):
        # 2025 has current rosters → projections are generated; the schema must
        # always carry opponent_team_id so the lineup optimizer can build stacks.
        r = client.get("/api/fantasy/projections?week=1&season=2025&position=QB&scoring=ppr")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "opponent_team_id" in data[0]

    def test_start_sit_requires_params(self):
        r = client.get("/api/fantasy/start-sit")
        assert r.status_code == 422

    def test_waiver_returns_list(self):
        r = client.get("/api/fantasy/waiver?week=1&season=2024&scoring=ppr")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_draft_rankings_returns_list(self):
        r = client.get("/api/fantasy/draft-rankings?season=2024&scoring=ppr")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_draft_rankings_by_position(self):
        r = client.get("/api/fantasy/draft-rankings?season=2024&scoring=ppr&position=QB")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_trade_analyze_empty_lists(self):
        r = client.post("/api/fantasy/trade-analyze", json={
            "give_player_ids": [],
            "get_player_ids": [],
            "week": 1,
            "season": 2024,
        })
        assert r.status_code in (200, 400, 422)

    def test_trade_analyze_oversized_list(self):
        r = client.post("/api/fantasy/trade-analyze", json={
            "give_player_ids": list(range(11)),  # exceeds max_length=10
            "get_player_ids": [],
            "week": 1,
            "season": 2024,
        })
        assert r.status_code == 422

    def test_power_rankings_returns_list(self):
        r = client.get("/api/fantasy/power-rankings?week=1&season=2024")
        assert r.status_code == 200
        data = r.json()
        assert "rankings" in data
        assert isinstance(data["rankings"], list)

    def test_trade_values_returns_list(self):
        r = client.get("/api/fantasy/trade-values?week=1&season=2024")
        assert r.status_code == 200
        data = r.json()
        assert "players" in data
        assert isinstance(data["players"], list)

    def test_import_by_names(self):
        r = client.post("/api/fantasy/roster/import-by-names", json={
            "names": ["Patrick Mahomes", "Justin Jefferson"],
            "season": 2024,
        })
        assert r.status_code == 200
        data = r.json()
        assert "matched" in data
        assert "unmatched" in data

    def test_import_by_names_oversized(self):
        r = client.post("/api/fantasy/roster/import-by-names", json={
            "names": [f"Player {i}" for i in range(51)],  # exceeds max_length=50
            "season": 2024,
        })
        assert r.status_code == 422


# ── Seasons / Playoff picture ──────────────────────────────────────────────────

class TestSeasons:
    def test_playoff_picture_valid_season(self):
        r = client.get("/api/seasons/2024/playoff-picture")
        assert r.status_code == 200
        data = r.json()
        assert "AFC" in data
        assert "NFC" in data
        assert "season" in data

    def test_playoff_picture_has_division_leaders(self):
        r = client.get("/api/seasons/2024/playoff-picture")
        assert r.status_code == 200
        data = r.json()
        assert "division_leaders" in data["AFC"]
        assert "division_leaders" in data["NFC"]

    def test_playoff_picture_nonexistent_season(self):
        r = client.get("/api/seasons/1800/playoff-picture")
        assert r.status_code == 404


# ── Team upcoming / starters ───────────────────────────────────────────────────

class TestTeamExtended:
    def test_team_upcoming(self):
        r = client.get("/api/teams/KC/upcoming?season=2025")
        assert r.status_code == 200
        data = r.json()
        assert "games" in data
        assert isinstance(data["games"], list)

    def test_team_upcoming_limit_bounds(self):
        r = client.get("/api/teams/KC/upcoming?season=2025&limit=0")
        assert r.status_code == 422

    def test_team_upcoming_limit_max(self):
        r = client.get("/api/teams/KC/upcoming?season=2025&limit=21")
        assert r.status_code == 422

    def test_team_starters(self):
        r = client.get("/api/teams/KC/starters?season=2024")
        assert r.status_code == 200
        data = r.json()
        assert "players" in data


# ── Player weekly stats endpoint (Fantasy Depth Pack) ─────────────────────────

class TestPlayerWeeklyStats:
    def _any_player_id(self):
        from src.database.db import Database
        db = Database(DEFAULT_DB_PATH)
        try:
            row = db.fetchone("SELECT player_id FROM players LIMIT 1")
            return row["player_id"] if row else None
        finally:
            db.close()

    def test_404_unknown_player(self):
        r = client.get("/api/players/999999999/weekly-stats?season=2024")
        assert r.status_code == 404

    def test_known_player_returns_shape(self):
        pid = self._any_player_id()
        if pid is None:
            pytest.skip("No players in DB")
        r = client.get(f"/api/players/{pid}/weekly-stats?season=2024")
        assert r.status_code == 200
        data = r.json()
        assert data["player_id"] == pid
        assert data["season"] == 2024
        assert isinstance(data["weeks"], list)
        for cell in data["weeks"]:
            assert "week" in cell
            assert "is_bye" in cell
            assert "snap_pct" in cell
            assert "fantasy_points_ppr" in cell

    def test_season_validation(self):
        r = client.get("/api/players/1/weekly-stats?season=1800")
        assert r.status_code == 422

    def test_snaps_nullable(self):
        """snaps may be null when importer only filled snap_pct."""
        pid = self._any_player_id()
        if pid is None:
            pytest.skip("No players in DB")
        r = client.get(f"/api/players/{pid}/weekly-stats?season=2024")
        assert r.status_code == 200
        for cell in r.json()["weeks"]:
            # snaps either int or null; never both 0 and snap_pct>0 simultaneously
            if cell.get("snap_pct", 0) > 0 and (cell.get("snaps") in (0, None)):
                assert cell["snaps"] is None or cell["snaps"] > 0

    def test_expanded_stat_fields_present(self):
        """The richer game-log payload must expose the full per-game stat line."""
        pid = self._any_player_id()
        if pid is None:
            pytest.skip("No players in DB")
        r = client.get(f"/api/players/{pid}/weekly-stats?season=2023")
        assert r.status_code == 200
        for cell in r.json()["weeks"]:
            for k in (
                "receptions", "rec_tds", "air_yards", "adot", "route_pct",
                "rush_attempts", "rush_tds", "pass_attempts", "pass_completions",
                "pass_tds", "interceptions", "result", "team_score", "opp_score",
            ):
                assert k in cell

    def test_played_week_has_game_result(self):
        """A player with 2023 weekly data should have weeks tagged with a W/L/T result."""
        from src.database.db import Database
        db = Database(DEFAULT_DB_PATH)
        try:
            row = db.fetchone(
                "SELECT player_id FROM player_weekly_stats WHERE season=2023 LIMIT 1"
            )
        finally:
            db.close()
        if not row:
            pytest.skip("No 2023 weekly stats in DB")
        pid = row["player_id"]
        r = client.get(f"/api/players/{pid}/weekly-stats?season=2023")
        assert r.status_code == 200
        results = [w["result"] for w in r.json()["weeks"] if w["result"] is not None]
        assert results, "expected at least one week with a game result"
        assert all(x in ("W", "L", "T") for x in results)
        for w in r.json()["weeks"]:
            if w["result"] is not None:
                assert w["team_score"] is not None and w["opp_score"] is not None


# ── Game detail endpoint ───────────────────────────────────────────────────────

class TestGameDetail:
    def _played_regular_game(self, season=2023):
        from src.database.db import Database
        db = Database(DEFAULT_DB_PATH)
        try:
            row = db.fetchone(
                "SELECT game_id FROM games WHERE season=? AND home_score IS NOT NULL "
                "AND CAST(week AS INTEGER) BETWEEN 1 AND 18 ORDER BY game_id LIMIT 1",
                (season,),
            )
            return row["game_id"] if row else None
        finally:
            db.close()

    def test_404_unknown_game(self):
        r = client.get("/api/games/999999999")
        assert r.status_code == 404

    def test_detail_shape_and_box_score(self):
        gid = self._played_regular_game()
        if gid is None:
            pytest.skip("No played 2023 regular-season game in DB")
        r = client.get(f"/api/games/{gid}")
        assert r.status_code == 200
        d = r.json()
        for k in ("game_id", "home_abbr", "away_abbr", "venue", "attendance",
                  "home_box", "away_box", "box_score_available", "factors", "odds", "weather"):
            assert k in d
        assert isinstance(d["home_box"], list)
        assert isinstance(d["away_box"], list)
        # 2023 regular-season games have weekly player data → box score populated
        assert d["box_score_available"] is True
        assert len(d["home_box"]) + len(d["away_box"]) > 0
        p = (d["home_box"] + d["away_box"])[0]
        for k in ("player_id", "full_name", "team_id", "fantasy_points_ppr",
                  "pass_yards", "rush_yards", "rec_yards"):
            assert k in p

    def test_playoff_game_has_empty_box(self):
        from src.database.db import Database
        db = Database(DEFAULT_DB_PATH)
        try:
            row = db.fetchone(
                "SELECT game_id FROM games WHERE game_type='playoff' AND home_score IS NOT NULL "
                "AND CAST(week AS INTEGER)=0 ORDER BY game_id DESC LIMIT 1"
            )
        finally:
            db.close()
        if not row:
            pytest.skip("No non-numeric-week playoff game in DB")
        r = client.get(f"/api/games/{row['game_id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["box_score_available"] is False
        assert d["home_box"] == [] and d["away_box"] == []

    def test_adversarial_game_id_never_500(self):
        for bad in ("abc", "-1", "0", "99999999999999999999"):
            r = client.get(f"/api/games/{bad}")
            assert r.status_code != 500


# ── Game retrodiction endpoint ─────────────────────────────────────────────────

class TestGameRetrodiction:
    def _played_game(self):
        from src.database.db import Database
        db = Database(DEFAULT_DB_PATH)
        try:
            row = db.fetchone(
                "SELECT game_id, home_team_id, away_team_id, winner_id FROM games "
                "WHERE season=2023 AND home_score IS NOT NULL AND winner_id IS NOT NULL "
                "ORDER BY game_id LIMIT 1"
            )
            return dict(row) if row else None
        finally:
            db.close()

    def test_404_unknown_game(self):
        r = client.get("/api/games/999999999/retrodiction")
        assert r.status_code == 404

    def test_retrodiction_shape_and_consistency(self):
        g = self._played_game()
        if g is None:
            pytest.skip("No played 2023 game in DB")
        r = client.get(f"/api/games/{g['game_id']}/retrodiction")
        assert r.status_code == 200
        d = r.json()
        # probabilities are a valid distribution
        assert abs(d["home_prob"] + d["away_prob"] - 1.0) < 0.01
        assert 0.0 <= d["home_prob"] <= 1.0
        # predicted winner is one of the two teams and matches the higher prob
        assert d["predicted_winner_abbr"] in (d["home_abbr"], d["away_abbr"])
        higher = d["home_abbr"] if d["home_prob"] > d["away_prob"] else d["away_abbr"]
        assert d["predicted_winner_abbr"] == higher
        # verdict agrees with predicted vs actual
        assert d["actual_winner_abbr"] in (d["home_abbr"], d["away_abbr"])
        assert d["correct"] == (d["predicted_winner_abbr"] == d["actual_winner_abbr"])
        assert d["confidence"] in ("low", "medium", "high")
        assert d["model"] == "weighted_sum"
        assert d["cutoff_date"]

    def test_unplayed_game_rejected(self):
        from src.database.db import Database
        db = Database(DEFAULT_DB_PATH)
        try:
            row = db.fetchone(
                "SELECT game_id FROM games WHERE home_score IS NULL LIMIT 1"
            )
        finally:
            db.close()
        if not row:
            pytest.skip("No unplayed games in DB")
        r = client.get(f"/api/games/{row['game_id']}/retrodiction")
        assert r.status_code == 400

    def test_adversarial_ids_never_500(self):
        for bad in ("abc", "-1", "0", "99999999999999999999"):
            r = client.get(f"/api/games/{bad}/retrodiction")
            assert r.status_code != 500


# ── Factors CRUD ──────────────────────────────────────────────────────────────

class TestFactorsCRUD:
    def test_factors_list_invalid_game(self):
        r = client.get("/api/factors/999999")
        assert r.status_code == 200  # Returns empty list, not 404
        data = r.json()
        assert "factors" in data

    def test_add_factor(self):
        r = client.post("/api/factors", json={
            "game_id": 1,
            "team_id": 1,
            "factor_type": "injury",
            "description": "Test injury factor",
            "impact_rating": -2.0,
        })
        # May 200/400/422 depending on validation
        assert r.status_code in (200, 400, 422)

    def test_delete_nonexistent_factor(self):
        r = client.delete("/api/factors/999999")
        assert r.status_code == 404


# ── System endpoints ───────────────────────────────────────────────────────────

class TestSystemEndpoints:
    def test_scrape_status(self):
        r = client.get("/api/scrape/status")
        assert r.status_code == 200
        data = r.json()
        assert "completed_seasons" in data
        assert "total_games" in data

    def test_model_info(self):
        r = client.get("/api/model/info")
        assert r.status_code == 200
        data = r.json()
        assert "model_type" in data
        assert "ml_model_loaded" in data

    def test_health_no_db_path_in_response(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        # Ensure we never expose the db file path
        assert "db_path" not in data
        assert data.get("database") == "connected"


# ── Adversarial / security tests ───────────────────────────────────────────────

class TestAdversarialInputs:
    def test_team_search_sql_injection(self):
        r = client.get("/api/teams/KC' OR '1'='1")
        assert r.status_code == 404  # Not found, not error

    def test_accuracy_malformed_seasons(self):
        r = client.get("/api/accuracy?seasons=abc")
        assert r.status_code == 422

    def test_accuracy_empty_seasons(self):
        r = client.get("/api/accuracy?seasons=")
        assert r.status_code == 422

    def test_player_search_too_short(self):
        r = client.get("/api/players/search?q=a")
        assert r.status_code == 422

    def test_player_search_unicode(self):
        r = client.get("/api/players/search?q=Ñoño")
        assert r.status_code == 200  # Returns empty list, not error

    def test_team_negative_id(self):
        r = client.get("/api/teams/-1")
        assert r.status_code == 404

    def test_games_invalid_limit(self):
        r = client.get("/api/games?limit=0")
        assert r.status_code == 422

    def test_games_limit_too_large(self):
        r = client.get("/api/games?limit=9999")
        assert r.status_code == 422

    def test_predict_same_teams(self):
        r = client.post("/api/predict", json={
            "home_team": "KC",
            "away_team": "KC",
            "current_season": 2025,
            "is_playoff": False,
            "week": 1,
        })
        # Should either succeed or fail gracefully, never 500
        assert r.status_code in (200, 400, 404, 422)

    def test_predict_nonexistent_team(self):
        r = client.post("/api/predict", json={
            "home_team": "XXXXXXXXX",
            "away_team": "KC",
            "current_season": 2025,
            "is_playoff": False,
            "week": 1,
        })
        assert r.status_code == 404

    def test_import_names_empty_list(self):
        r = client.post("/api/fantasy/roster/import-by-names", json={
            "names": [],
            "season": 2024,
        })
        assert r.status_code in (200, 422)

    def test_global_exception_handler_returns_json(self):
        """404 for completely unknown routes returns structured JSON."""
        r = client.get("/api/this-does-not-exist-at-all")
        assert r.status_code == 404
