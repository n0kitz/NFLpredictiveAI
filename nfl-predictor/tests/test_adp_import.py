"""Tests for real-ADP ingestion (scripts/import_adp.py + player_adp table)."""

import pytest

from src.database.db import Database
from src.scraper.adp_importer import parse_adp_csv, import_adp

FANTASYPROS_CSV = """"RK","TIERS","PLAYER NAME","TEAM","POSITION","BYE WEEK","SOS SEASON","ECR VS. ADP"
"1","1","Saquon Barkley","PHI","RB1","9","3 out of 5 stars","0"
"2","1","Ja'Marr Chase","CIN","WR1","10","4 out of 5 stars","+1"
"3","2","Lamar Jackson","BAL","QB1","7","3 out of 5 stars","-1"
"""

SIMPLE_CSV = """name,adp
Saquon Barkley,1.2
Ja'Marr Chase,2.8
"""


class TestParseAdpCsv:
    def test_fantasypros_format_uses_rank_as_adp(self):
        rows = parse_adp_csv(FANTASYPROS_CSV)
        assert rows[0] == ("Saquon Barkley", 1.0)
        assert rows[1] == ("Ja'Marr Chase", 2.0)
        assert rows[2][0] == "Lamar Jackson"

    def test_simple_name_adp_format(self):
        rows = parse_adp_csv(SIMPLE_CSV)
        assert rows == [("Saquon Barkley", 1.2), ("Ja'Marr Chase", 2.8)]

    def test_position_strings_ignored(self):
        rows = parse_adp_csv(FANTASYPROS_CSV)
        assert all(isinstance(a, float) for _, a in rows)

    def test_empty_input(self):
        assert parse_adp_csv("") == []


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


class TestImportAdp:
    def test_upserts_matched_players(self, tmp_db):
        cur = tmp_db.execute(
            "INSERT INTO players (espn_id, full_name, last_name, position) "
            "VALUES ('X1', 'Saquon Barkley', 'Barkley', 'RB')",
            (),
        )
        pid = cur.lastrowid
        tmp_db.commit()

        matched, unmatched = import_adp(tmp_db, SIMPLE_CSV, season=2026)
        assert matched == 1
        assert unmatched == ["Ja'Marr Chase"]
        row = tmp_db.fetchone(
            "SELECT adp FROM player_adp WHERE season = 2026 AND player_id = ?",
            (pid,),
        )
        assert row["adp"] == 1.2
