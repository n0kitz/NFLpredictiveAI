"""Tests for player-name normalization in the shared name matcher.

Upstream feeds spell names inconsistently: FFC sends "Kenneth Walker" where
we store "Kenneth Walker III", and "Eddy Piñeiro" where we store
"Eddy Pineiro". Those misses are silent — the player simply drops out of the
import — so the matcher folds accents and generational suffixes before
giving up.
"""

import pytest

from src.database.db import Database
from src.scraper.player_weekly_importer import _match_player_id, normalize_player_name


class TestNormalizePlayerName:
    def test_lowercases(self):
        assert normalize_player_name("Bijan Robinson") == "bijan robinson"

    def test_folds_accents(self):
        assert normalize_player_name("Eddy Piñeiro") == normalize_player_name(
            "Eddy Pineiro"
        )

    @pytest.mark.parametrize("suffix", ["Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV"])
    def test_strips_generational_suffixes(self, suffix):
        assert normalize_player_name(f"Kenneth Walker {suffix}") == "kenneth walker"

    def test_strips_punctuation(self):
        assert normalize_player_name("Ja'Marr Chase") == "jamarr chase"
        assert normalize_player_name("Amon-Ra St. Brown") == "amon ra st brown"

    def test_collapses_whitespace(self):
        assert normalize_player_name("  Puka   Nacua  ") == "puka nacua"

    def test_empty_input(self):
        assert normalize_player_name("") == ""


@pytest.fixture
def tmp_db(tmp_path):
    db = Database(tmp_path / "test.db")
    for espn_id, full, last, pos in [
        ("1", "Kenneth Walker III", "Walker III", "RB"),
        ("2", "Eddy Pineiro", "Pineiro", "K"),
        ("3", "Puka Nacua", "Nacua", "WR"),
        ("4", "Mike Williams", "Williams", "WR"),
        ("5", "Mike Williams", "Williams", "TE"),
        # The pair that corrupted the 2026 ADP import: two RBs sharing a last
        # name, one of them stored with a suffix the feed omits.
        ("6", "Bijan Robinson", "Robinson", "RB"),
        ("7", "Brian Robinson Jr.", "Robinson Jr.", "RB"),
    ]:
        db.execute(
            "INSERT INTO players (espn_id, full_name, last_name, position) "
            "VALUES (?, ?, ?, ?)",
            (espn_id, full, last, pos),
        )
    db.commit()
    yield db
    db.close()


class TestMatchPlayerId:
    def test_exact_name_still_matches(self, tmp_db):
        assert _match_player_id(tmp_db, "Puka Nacua", "WR") is not None

    def test_suffix_dropped_upstream_still_matches(self, tmp_db):
        pid = _match_player_id(tmp_db, "Kenneth Walker", "RB")
        row = tmp_db.fetchone(
            "SELECT full_name FROM players WHERE player_id = ?", (pid,)
        )
        assert row["full_name"] == "Kenneth Walker III"

    def test_accented_name_matches_unaccented_row(self, tmp_db):
        pid = _match_player_id(tmp_db, "Eddy Piñeiro", "K")
        row = tmp_db.fetchone(
            "SELECT full_name FROM players WHERE player_id = ?", (pid,)
        )
        assert row["full_name"] == "Eddy Pineiro"

    def test_position_disambiguates_duplicate_names(self, tmp_db):
        pid = _match_player_id(tmp_db, "Mike Williams", "TE")
        row = tmp_db.fetchone(
            "SELECT position FROM players WHERE player_id = ?", (pid,)
        )
        assert row["position"] == "TE"

    def test_ambiguous_normalized_match_returns_none(self, tmp_db):
        # Two Mike Williamses and no position to separate them: refuse to guess.
        assert _match_player_id(tmp_db, "Mike Williams ", "") is None

    def test_unknown_player_returns_none(self, tmp_db):
        assert _match_player_id(tmp_db, "Nobody At All", "WR") is None

    def test_shared_last_name_does_not_bind_to_the_wrong_player(self, tmp_db):
        """The 2026 ADP corruption: "Brian Robinson" took Bijan's row.

        Our table holds "Brian Robinson Jr."; the feed omits the suffix. The
        last-name fallback matched last_name='Robinson' + RB with LIMIT 1 and
        returned Bijan, so Bijan's ADP of 2.2 was overwritten with 107.0.
        """
        bijan = _match_player_id(tmp_db, "Bijan Robinson", "RB")
        brian = _match_player_id(tmp_db, "Brian Robinson", "RB")
        assert bijan is not None and brian is not None
        assert bijan != brian

        row = tmp_db.fetchone(
            "SELECT full_name FROM players WHERE player_id = ?", (brian,)
        )
        assert row["full_name"] == "Brian Robinson Jr."

    def test_last_name_fallback_refuses_when_ambiguous(self, tmp_db):
        # "Robinson" alone matches two RBs and no first name separates them.
        assert _match_player_id(tmp_db, "Robinson", "RB") is None

    def test_unique_last_name_still_needs_a_compatible_first_name(self, tmp_db):
        """A player we don't carry must not inherit a namesake's row.

        Real case: the 2025 feed has Russell Wilson, our roster table only has
        Zach Wilson. "Wilson" + QB is unique in our table, so a uniqueness
        check alone still produced a confident, wrong match.
        """
        tmp_db.execute(
            "INSERT INTO players (espn_id, full_name, last_name, position) "
            "VALUES ('8', 'Zach Wilson', 'Wilson', 'QB')",
            (),
        )
        tmp_db.commit()
        assert _match_player_id(tmp_db, "Russell Wilson", "QB") is None
        assert _match_player_id(tmp_db, "Zach Wilson", "QB") is not None

    def test_shortened_first_name_still_matches(self, tmp_db):
        # Feeds shorten first names; "Josh" and "Joshua" are the same player.
        tmp_db.execute(
            "INSERT INTO players (espn_id, full_name, last_name, position) "
            "VALUES ('9', 'Joshua Palmer', 'Palmer', 'WR')",
            (),
        )
        tmp_db.commit()
        assert _match_player_id(tmp_db, "Josh Palmer", "WR") is not None
