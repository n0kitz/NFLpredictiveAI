"""API endpoint tests using FastAPI TestClient against the real database."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.database.db import DEFAULT_DB_PATH


# Skip entire module if the real database doesn't exist
pytestmark = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(),
    reason="Real database not found — run scraper first",
)

client = TestClient(app)


# ── Health ────────────────────────────────────────────


class TestHealth:
    def test_health_ok(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["total_teams"] >= 32
        assert data["total_games"] > 0


# ── Teams ─────────────────────────────────────────────


class TestTeams:
    def test_list_teams(self):
        r = client.get("/api/teams")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 32
        assert len(data["teams"]) == data["count"]

    def test_get_team_by_abbr(self):
        r = client.get("/api/teams/KC")
        assert r.status_code == 200
        data = r.json()
        assert data["abbreviation"] == "KC"
        assert data["name"] == "Chiefs"

    def test_get_team_by_name(self):
        r = client.get("/api/teams/Eagles")
        assert r.status_code == 200
        assert r.json()["abbreviation"] == "PHI"

    def test_get_team_not_found(self):
        r = client.get("/api/teams/ZZZZZ")
        assert r.status_code == 404

    def test_team_stats(self):
        r = client.get("/api/teams/KC/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["team_abbr"] == "KC"
        assert 0 <= data["win_percentage"] <= 1
        assert data["games_analyzed"] > 0
        # New fields from Batch 1
        assert 0 <= data["strength_of_schedule"] <= 1
        assert 0 <= data["dynamic_hfa"] <= 0.10
        assert data["rest_days"] >= 0

    def test_team_stats_not_found(self):
        r = client.get("/api/teams/ZZZZZ/stats")
        assert r.status_code == 404

    def test_team_profile(self):
        r = client.get("/api/teams/KC/profile")
        assert r.status_code == 200
        data = r.json()
        assert data["team_abbr"] == "KC"
        assert data["all_time"]["games_played"] > 0
        assert data["last_season"] is not None
        assert data["last_season_year"] is not None

    def test_team_profile_not_found(self):
        r = client.get("/api/teams/ZZZZZ/profile")
        assert r.status_code == 404

    def test_team_season_2025(self):
        r = client.get("/api/teams/KC/season/2025")
        assert r.status_code == 200
        data = r.json()
        assert data["season"] == 2025
        assert data["games_played"] > 0

    def test_team_season_not_found(self):
        r = client.get("/api/teams/KC/season/1800")
        assert r.status_code == 404


# ── Games ─────────────────────────────────────────────


class TestGames:
    def test_list_games(self):
        r = client.get("/api/games")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] > 0

    def test_games_by_season(self):
        r = client.get("/api/games?season=2024")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] > 0
        assert all(g["season"] == 2024 for g in data["games"])

    def test_team_games(self):
        r = client.get("/api/teams/KC/games?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] <= 5

    def test_team_games_not_found(self):
        r = client.get("/api/teams/ZZZZZ/games")
        assert r.status_code == 404


# ── Predictions ───────────────────────────────────────


class TestPredictions:
    def test_predict_post(self):
        r = client.post("/api/predict", json={
            "home_team": "KC",
            "away_team": "PHI",
        })
        assert r.status_code == 200
        data = r.json()
        assert 0.02 <= data["home_win_probability"] <= 0.98
        assert 0.02 <= data["away_win_probability"] <= 0.98
        assert abs(data["home_win_probability"] + data["away_win_probability"] - 1.0) < 0.001
        assert data["confidence"] in ("low", "medium", "high")
        assert data["predicted_winner"] in (data["home_team"], data["away_team"])
        assert len(data["key_factors"]) > 0

    def test_predict_get(self):
        r = client.get("/api/predict/PHI/KC")
        assert r.status_code == 200
        data = r.json()
        assert 0.02 <= data["home_win_probability"] <= 0.98
        assert abs(data["home_win_probability"] + data["away_win_probability"] - 1.0) < 0.001

    def test_predict_invalid_team(self):
        r = client.post("/api/predict", json={
            "home_team": "ZZZZZ",
            "away_team": "KC",
        })
        assert r.status_code == 404

    def test_predict_get_invalid(self):
        r = client.get("/api/predict/ZZZZZ/KC")
        assert r.status_code == 404


# ── Head-to-Head ──────────────────────────────────────


class TestH2H:
    def test_h2h(self):
        r = client.get("/api/h2h/KC/PHI")
        assert r.status_code == 200
        data = r.json()
        assert data["total_games"] >= 0
        assert data["team1_abbr"] == "KC"
        assert data["team2_abbr"] == "PHI"

    def test_h2h_not_found(self):
        r = client.get("/api/h2h/ZZZZZ/KC")
        assert r.status_code == 404


# ── Accuracy ──────────────────────────────────────────


class TestAccuracy:
    def test_accuracy_endpoint(self):
        r = client.get("/api/accuracy?seasons=2025")
        assert r.status_code == 200
        data = r.json()
        assert data["total_games"] > 0
        assert 0 <= data["accuracy"] <= 1


# ── Factors ───────────────────────────────────────────


class TestFactors:
    def test_factors_empty(self):
        # game_id=999999 is unlikely to exist
        r = client.get("/api/factors/999999")
        assert r.status_code == 200
        assert r.json()["count"] == 0


# ── Vegas Odds ─────────────────────────────────────────


class TestGameOdds:
    def test_game_odds_not_found(self):
        """Requesting odds for a non-existent game returns 404."""
        r = client.get("/api/games/999999/odds")
        assert r.status_code == 404

    def test_game_odds_malformed_id(self):
        """Non-integer game_id returns 422 Unprocessable Entity."""
        r = client.get("/api/games/not-a-number/odds")
        assert r.status_code == 422

    def test_predict_response_has_vegas_context_field(self):
        """POST /api/predict always includes vegas_context key (None when no odds stored)."""
        r = client.post("/api/predict", json={
            "home_team": "KC",
            "away_team": "PHI",
        })
        assert r.status_code == 200
        data = r.json()
        # Field must be present; value is None when no odds are in the DB
        assert "vegas_context" in data


# ── Conditions ──────────────────────────────────────────


class TestGameConditions:
    def test_conditions_endpoint_not_found(self):
        """Requesting conditions for a non-existent game returns 404."""
        r = client.get("/api/games/999999/conditions")
        assert r.status_code == 404

    def test_conditions_endpoint_found(self):
        """Conditions endpoint for a real game returns the expected structure."""
        # Get any real game_id from the DB
        games_r = client.get("/api/games?limit=1")
        assert games_r.status_code == 200
        games_data = games_r.json()
        if not games_data["games"]:
            pytest.skip("No games in DB")

        game_id = games_data["games"][0]["game_id"]
        r = client.get(f"/api/games/{game_id}/conditions")
        assert r.status_code == 200
        data = r.json()
        assert data["game_id"] == game_id
        assert "conditions" in data
        cond = data["conditions"]
        assert "home_injuries" in cond
        assert "away_injuries" in cond
        assert "weather" in cond  # may be None if not yet fetched

    def test_predict_response_has_conditions_field(self):
        """POST /api/predict includes a conditions key."""
        r = client.post("/api/predict", json={
            "home_team": "KC",
            "away_team": "PHI",
        })
        assert r.status_code == 200
        data = r.json()
        assert "conditions" in data


# ── SHAP Explanation ─────────────────────────────────────


class TestExplainEndpoint:
    def test_explain_endpoint_exists(self):
        """POST /api/predict/explain returns 200 for valid teams."""
        r = client.post("/api/predict/explain", json={
            "home_team": "KC",
            "away_team": "PHI",
        })
        assert r.status_code == 200

    def test_explain_response_has_explanation_key(self):
        """Response from /api/predict/explain contains an 'explanation' list."""
        r = client.post("/api/predict/explain", json={
            "home_team": "KC",
            "away_team": "PHI",
        })
        assert r.status_code == 200
        data = r.json()
        assert "explanation" in data
        assert isinstance(data["explanation"], list)


# ── Roster & Players ──────────────────────────────────


class TestRosterEndpoints:
    def test_team_roster_returns_valid_shape(self):
        """GET /api/teams/{id}/roster returns team_abbr, season, players, count."""
        r = client.get("/api/teams/KC/roster")
        assert r.status_code == 200
        data = r.json()
        assert "team_abbr" in data
        assert "season" in data
        assert "players" in data
        assert "count" in data
        assert isinstance(data["players"], list)

    def test_player_search_returns_list(self):
        """GET /api/players/search?q=... returns a list."""
        r = client.get("/api/players/search?q=Patrick")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_player_not_found_returns_404(self):
        """GET /api/players/999999999 returns 404 for unknown id."""
        r = client.get("/api/players/999999999")
        assert r.status_code == 404

    def test_fantasy_top_returns_leaderboard(self):
        """GET /api/fantasy/top returns position, season, players list."""
        r = client.get("/api/fantasy/top?position=QB&season=2024")
        assert r.status_code == 200
        data = r.json()
        assert data["position"] == "QB"
        assert data["season"] == 2024
        assert "players" in data
        assert isinstance(data["players"], list)


# ── Value Picks ────────────────────────────────────────


class TestValuePicks:
    def test_value_picks_returns_valid_shape(self):
        """GET /api/picks/value returns picks list, generated_at, and note."""
        r = client.get("/api/picks/value")
        assert r.status_code == 200
        data = r.json()
        assert "picks" in data
        assert "generated_at" in data
        assert "note" in data
        assert isinstance(data["picks"], list)
        assert isinstance(data["note"], str)

    def test_value_picks_each_pick_has_required_fields(self):
        """Each pick in /api/picks/value has the required schema fields."""
        r = client.get("/api/picks/value")
        assert r.status_code == 200
        picks = r.json()["picks"]
        for pick in picks:
            assert "game_id" in pick
            assert "game_date" in pick
            assert "home_team" in pick
            assert "away_team" in pick
            assert "model_home_prob" in pick
            assert "vegas_home_implied_prob" in pick
            assert "edge" in pick
            assert "edge_side" in pick
            assert pick["edge_side"] in ("home", "away")
            assert "model_confidence" in pick
            assert pick["model_confidence"] in ("HIGH", "MEDIUM", "LOW")
            assert abs(pick["edge"]) >= 0.04

    def test_value_picks_sorted_by_abs_edge(self):
        """Picks are returned sorted by absolute edge descending."""
        r = client.get("/api/picks/value")
        assert r.status_code == 200
        picks = r.json()["picks"]
        if len(picks) < 2:
            return
        edges = [abs(p["edge"]) for p in picks]
        assert edges == sorted(edges, reverse=True)
