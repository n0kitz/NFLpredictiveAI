"""Tests for live ADP ingestion from the Fantasy Football Calculator API.

The CSV path (``tests/test_adp_import.py``) requires a manual download; this
path fetches current consensus ADP directly so ``player_adp`` can be filled
without leaving the terminal.
"""

import json

import pytest

from src.database.db import Database
from src.scraper.adp_importer import (
    AdpEntry,
    FFC_SCORING,
    evaluate_adp_import,
    fetch_ffc_adp,
    ffc_url,
    import_adp_entries,
    parse_ffc_adp,
)

PAYLOAD = {
    "status": "Success",
    "meta": {"type": "Non-PPR", "teams": 10, "total_drafts": 1480},
    "players": [
        {"name": "Jahmyr Gibbs", "position": "RB", "team": "DET", "adp": 1.5},
        {"name": "Brandon Aubrey", "position": "PK", "team": "DAL", "adp": 130.9},
        {"name": "Seattle Defense", "position": "DEF", "team": "SEA", "adp": 80.1},
    ],
}


class TestFfcUrl:
    def test_standard_scoring_maps_to_ffc_format(self):
        url = ffc_url(season=2026, scoring="standard", teams=10)
        assert "/adp/standard?" in url
        assert "year=2026" in url
        assert "teams=10" in url

    def test_half_ppr_underscore_maps_to_hyphen(self):
        assert "/adp/half-ppr?" in ffc_url(season=2026, scoring="half_ppr", teams=12)

    def test_ppr_supported(self):
        assert "/adp/ppr?" in ffc_url(season=2026, scoring="ppr", teams=12)

    def test_unknown_scoring_rejected(self):
        with pytest.raises(ValueError):
            ffc_url(season=2026, scoring="superflex", teams=10)

    def test_every_supported_scoring_has_a_mapping(self):
        for scoring in ("standard", "half_ppr", "ppr"):
            assert scoring in FFC_SCORING


class TestParseFfcAdp:
    def test_returns_entries_with_name_position_team_adp(self):
        entries = parse_ffc_adp(PAYLOAD)
        assert entries[0] == AdpEntry("Jahmyr Gibbs", "RB", "DET", 1.5)

    def test_kicker_position_pk_normalized_to_k(self):
        entries = parse_ffc_adp(PAYLOAD)
        assert entries[1].position == "K"

    def test_defense_position_def_normalized_to_dst(self):
        entries = parse_ffc_adp(PAYLOAD)
        assert entries[2].position == "DST"

    def test_rows_without_name_or_adp_skipped(self):
        payload = {
            "players": [
                {"name": "", "position": "RB", "team": "DET", "adp": 1.5},
                {"name": "No ADP", "position": "RB", "team": "DET"},
                {"name": "Fine", "position": "RB", "team": "DET", "adp": "3.2"},
            ]
        }
        entries = parse_ffc_adp(payload)
        assert [e.name for e in entries] == ["Fine"]
        assert entries[0].adp == 3.2

    def test_empty_payload(self):
        assert parse_ffc_adp({}) == []
        assert parse_ffc_adp({"players": []}) == []


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.headers: dict = {}

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self._response


class TestFetchFfcAdp:
    def test_fetches_and_parses(self):
        session = _FakeSession(_FakeResponse(PAYLOAD))
        entries = fetch_ffc_adp(season=2026, scoring="standard", session=session)
        assert [e.name for e in entries] == [
            "Jahmyr Gibbs",
            "Brandon Aubrey",
            "Seattle Defense",
        ]
        assert "year=2026" in session.calls[0][0]

    def test_non_200_raises(self):
        # 404 rather than 503: a permanent error returns immediately, while a
        # retryable status would make the test sleep through the backoff.
        session = _FakeSession(_FakeResponse({}, status_code=404))
        with pytest.raises(RuntimeError):
            fetch_ffc_adp(season=2026, scoring="standard", session=session)


@pytest.fixture
def tmp_db(tmp_path):
    from src.scraper.team_mappings import CURRENT_TEAMS

    db = Database(tmp_path / "test.db")
    for t in CURRENT_TEAMS:
        db.insert_team(
            t.name,
            t.city,
            t.conference,
            t.division,
            t.abbreviation,
            t.franchise_id,
            t.active_from,
            t.active_until,
        )
    yield db
    db.close()


class TestImportAdpEntries:
    def test_matches_offensive_player_by_name(self, tmp_db):
        cur = tmp_db.execute(
            "INSERT INTO players (espn_id, full_name, last_name, position) "
            "VALUES ('X1', 'Jahmyr Gibbs', 'Gibbs', 'RB')",
            (),
        )
        pid = cur.lastrowid
        tmp_db.commit()

        matched, unmatched = import_adp_entries(
            tmp_db, [AdpEntry("Jahmyr Gibbs", "RB", "DET", 1.5)], season=2026
        )
        assert matched == 1
        assert unmatched == []
        row = tmp_db.fetchone(
            "SELECT adp, source FROM player_adp WHERE season = 2026 AND player_id = ?",
            (pid,),
        )
        assert row["adp"] == 1.5

    def test_defense_matched_to_synthetic_dst_player_by_team(self, tmp_db):
        cur = tmp_db.execute(
            "INSERT INTO players (espn_id, full_name, last_name, position) "
            "VALUES ('DST-SEA', 'Seahawks D/ST', 'D/ST', 'DST')",
            (),
        )
        pid = cur.lastrowid
        tmp_db.commit()

        matched, unmatched = import_adp_entries(
            tmp_db, [AdpEntry("Seattle Defense", "DST", "SEA", 80.1)], season=2026
        )
        assert matched == 1
        row = tmp_db.fetchone(
            "SELECT adp FROM player_adp WHERE season = 2026 AND player_id = ?",
            (pid,),
        )
        assert row["adp"] == 80.1

    def test_unmatched_names_reported(self, tmp_db):
        matched, unmatched = import_adp_entries(
            tmp_db, [AdpEntry("Nobody Here", "WR", "DET", 12.0)], season=2026
        )
        assert matched == 0
        assert unmatched == ["Nobody Here"]

    def test_reimport_updates_instead_of_duplicating(self, tmp_db):
        tmp_db.execute(
            "INSERT INTO players (espn_id, full_name, last_name, position) "
            "VALUES ('X1', 'Jahmyr Gibbs', 'Gibbs', 'RB')",
            (),
        )
        tmp_db.commit()
        entry = AdpEntry("Jahmyr Gibbs", "RB", "DET", 1.5)
        import_adp_entries(tmp_db, [entry], season=2026)
        import_adp_entries(tmp_db, [entry._replace(adp=2.4)], season=2026)

        rows = tmp_db.fetchall("SELECT adp FROM player_adp WHERE season = 2026", ())
        assert len(rows) == 1
        assert rows[0]["adp"] == 2.4


class TestEvaluateAdpImport:
    def test_zero_matches_is_a_failure(self):
        ok, message = evaluate_adp_import(matched=0, total=211)
        assert ok is False
        assert "0/211" in message

    def test_low_match_rate_warns_but_succeeds(self):
        ok, message = evaluate_adp_import(matched=100, total=211)
        assert ok is True
        assert "PARTIAL" in message

    def test_high_match_rate_is_ok(self):
        ok, message = evaluate_adp_import(matched=205, total=211)
        assert ok is True
        assert message.startswith("OK")
