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
