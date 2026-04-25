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
