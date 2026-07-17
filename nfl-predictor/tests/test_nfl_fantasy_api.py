"""Tests for the experimental fantasy.nfl.com client (fixtures only, no network)."""

from src.scraper.nfl_fantasy_api import (
    parse_league_settings,
    parse_league_rosters,
)

LEAGUE_JSON = {
    "leagues": [
        {
            "id": "1234567",
            "name": "Kitzmann League",
            "size": 12,
            "scoringSettings": {
                "receptionPoints": 0,
            },
            "teams": [
                {
                    "id": "1",
                    "name": "Team Normen",
                    "roster": {
                        "players": [
                            {"name": "Saquon Barkley", "position": "RB"},
                            {"name": "Jason Myers", "position": "K"},
                        ]
                    },
                },
                {
                    "id": "2",
                    "name": "Rival",
                    "roster": {
                        "players": [
                            {"name": "Josh Allen", "position": "QB"},
                        ]
                    },
                },
            ],
        }
    ]
}


class TestParseLeagueSettings:
    def test_extracts_name_size_scoring(self):
        s = parse_league_settings(LEAGUE_JSON)
        assert s == {
            "league_id": "1234567",
            "name": "Kitzmann League",
            "league_size": 12,
            "scoring": "standard",
        }

    def test_ppr_detection(self):
        data = {
            "leagues": [
                {
                    "id": "1",
                    "name": "x",
                    "size": 10,
                    "scoringSettings": {"receptionPoints": 1},
                }
            ]
        }
        assert parse_league_settings(data)["scoring"] == "ppr"

    def test_half_ppr_detection(self):
        data = {
            "leagues": [
                {
                    "id": "1",
                    "name": "x",
                    "size": 10,
                    "scoringSettings": {"receptionPoints": 0.5},
                }
            ]
        }
        assert parse_league_settings(data)["scoring"] == "half_ppr"

    def test_missing_league_returns_none(self):
        assert parse_league_settings({}) is None
        assert parse_league_settings({"leagues": []}) is None

    def test_size_clamped_to_supported_range(self):
        data = {"leagues": [{"id": "1", "name": "x", "size": 99}]}
        assert parse_league_settings(data)["league_size"] == 20


class TestParseLeagueRosters:
    def test_extracts_teams_and_players(self):
        teams = parse_league_rosters(LEAGUE_JSON)
        assert len(teams) == 2
        assert teams[0]["team_name"] == "Team Normen"
        assert ("Saquon Barkley", "RB") in teams[0]["players"]
        assert teams[1]["players"] == [("Josh Allen", "QB")]

    def test_empty_input(self):
        assert parse_league_rosters({}) == []


class TestSyncEndpoint:
    def _client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app

        return TestClient(app)

    def test_503_when_unavailable(self, monkeypatch):
        monkeypatch.delenv("NFL_FANTASY_COOKIE", raising=False)
        r = self._client().get("/api/nfl-league/1234567")
        assert r.status_code == 503
        assert "manual" in r.json()["detail"].lower()

    def test_returns_settings_and_teams(self, monkeypatch):
        import src.scraper.nfl_fantasy_api as mod

        monkeypatch.setattr(mod, "fetch_league", lambda league_id: LEAGUE_JSON)
        r = self._client().get("/api/nfl-league/1234567")
        assert r.status_code == 200
        body = r.json()
        assert body["experimental"] is True
        assert body["settings"]["scoring"] == "standard"
        assert body["settings"]["league_size"] == 12
        assert len(body["teams"]) == 2
