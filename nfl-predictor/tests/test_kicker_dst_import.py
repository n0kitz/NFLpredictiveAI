"""Tests for kicker + DST weekly imports from the nflverse stats_player_week feed.

Pure row-builders and scoring math are tested with fixture DataFrames (no
network). DB integration uses a temp database (schema.sql + migrations run on
connect).
"""

import pandas as pd
import pytest

from src.database.db import Database
from src.scraper.player_weekly_importer import (
    aggregate_kicker_dst_season_stats,
    build_kicker_week_rows,
    kicker_fantasy_points,
)
from src.scraper.dst_importer import (
    build_dst_week_rows,
    dst_fantasy_points,
    dst_points_allowed_score,
    ensure_dst_players,
)

# ── Kicker scoring ────────────────────────────────────────────────────────────


class TestKickerFantasyPoints:
    def test_fg_under_50_scores_3(self):
        assert (
            kicker_fantasy_points(fg_0_39=1, fg_40_49=1, fg_50_plus=0, xp_made=0) == 6.0
        )

    def test_fg_50_plus_scores_5(self):
        assert (
            kicker_fantasy_points(fg_0_39=0, fg_40_49=0, fg_50_plus=2, xp_made=0)
            == 10.0
        )

    def test_xp_scores_1(self):
        assert (
            kicker_fantasy_points(fg_0_39=0, fg_40_49=0, fg_50_plus=0, xp_made=4) == 4.0
        )

    def test_combined(self):
        # 2×3 + 1×5 + 3×1 = 14
        assert (
            kicker_fantasy_points(fg_0_39=1, fg_40_49=1, fg_50_plus=1, xp_made=3)
            == 14.0
        )


def _kicker_df(rows):
    """Minimal stats_player_week-shaped frame for kicker tests."""
    defaults = {
        "season_type": "REG",
        "position": "K",
        "player_display_name": "Test Kicker",
        "team": "KC",
        "opponent_team": "LV",
        "season": 2025,
        "week": 1,
        "fg_made_0_19": 0,
        "fg_made_20_29": 0,
        "fg_made_30_39": 0,
        "fg_made_40_49": 0,
        "fg_made_50_59": 0,
        "fg_made_60_": 0,
        "fg_missed": 0,
        "pat_made": 0,
        "pat_missed": 0,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


class TestBuildKickerWeekRows:
    def test_buckets_collapse_correctly(self):
        df = _kicker_df(
            [
                {
                    "fg_made_0_19": 1,
                    "fg_made_20_29": 1,
                    "fg_made_30_39": 1,
                    "fg_made_40_49": 1,
                    "fg_made_50_59": 1,
                    "fg_made_60_": 1,
                    "pat_made": 2,
                    "fg_missed": 1,
                }
            ]
        )
        rows = build_kicker_week_rows(df)
        assert len(rows) == 1
        r = rows[0]
        assert r["fg_made_0_39"] == 3
        assert r["fg_made_40_49"] == 1
        assert r["fg_made_50_plus"] == 2
        assert r["fg_missed"] == 1
        assert r["xp_made"] == 2
        # 3×3 + 1×3 + 2×5 + 2×1 = 24
        assert r["fantasy_points"] == 24.0

    def test_filters_non_kickers_and_postseason(self):
        df = _kicker_df(
            [
                {"fg_made_30_39": 1},
                {"position": "QB", "fg_made_30_39": 1},
                {"season_type": "POST", "fg_made_30_39": 1},
            ]
        )
        rows = build_kicker_week_rows(df)
        assert len(rows) == 1

    def test_carries_identity_fields(self):
        df = _kicker_df([{"fg_made_40_49": 1, "week": 7}])
        r = build_kicker_week_rows(df)[0]
        assert r["full_name"] == "Test Kicker"
        assert r["position"] == "K"
        assert r["team_abbr"] == "KC"
        assert r["opp_abbr"] == "LV"
        assert r["season"] == 2025
        assert r["week"] == 7


# ── DST scoring ───────────────────────────────────────────────────────────────


class TestDstPointsAllowedScore:
    @pytest.mark.parametrize(
        "pa,expected",
        [
            (0, 10),
            (1, 7),
            (6, 7),
            (7, 4),
            (13, 4),
            (14, 1),
            (20, 1),
            (21, 0),
            (27, 0),
            (28, -1),
            (34, -1),
            (35, -4),
            (50, -4),
        ],
    )
    def test_brackets(self, pa, expected):
        assert dst_points_allowed_score(pa) == expected


class TestDstFantasyPoints:
    def test_event_scoring(self):
        # 3 sacks(3) + 2 int(4) + 1 fum(2) + 1 td(6) + 1 safety(2) + 1 block(2)
        # + shutout(10) = 29
        pts = dst_fantasy_points(
            sacks=3,
            interceptions=2,
            fumbles_recovered=1,
            tds=1,
            safeties=1,
            blocks=1,
            points_allowed=0,
        )
        assert pts == 29.0

    def test_high_points_allowed_negative(self):
        assert dst_fantasy_points(0, 0, 0, 0, 0, 0, points_allowed=42) == -4.0


def _dst_df(rows):
    """Minimal stats_player_week-shaped frame for DST aggregation tests."""
    defaults = {
        "season_type": "REG",
        "position": "LB",
        "team": "KC",
        "opponent_team": "LV",
        "season": 2025,
        "week": 1,
        "def_sacks": 0.0,
        "def_interceptions": 0,
        "fumble_recovery_opp": 0,
        "def_tds": 0,
        "def_safeties": 0,
        "special_teams_tds": 0,
        "fg_blocked": 0,
        "pat_blocked": 0,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


class TestBuildDstWeekRows:
    PA = {("KC", 2025, 1): 13, ("LV", 2025, 1): 27}

    def test_aggregates_team_week(self):
        df = _dst_df(
            [
                {"def_sacks": 1.5, "def_interceptions": 1},
                {"def_sacks": 0.5, "fumble_recovery_opp": 1, "def_tds": 1},
            ]
        )
        rows = build_dst_week_rows(df, self.PA)
        kc = [r for r in rows if r["team_abbr"] == "KC"]
        assert len(kc) == 1
        r = kc[0]
        assert r["dst_sacks"] == 2  # 1.5 + 0.5 rounded to int
        assert r["dst_interceptions"] == 1
        assert r["dst_fumbles_recovered"] == 1
        assert r["dst_tds"] == 1
        assert r["dst_points_allowed"] == 13
        # 2 sacks(2) + int(2) + fum(2) + td(6) + PA 13(4) = 16
        assert r["fantasy_points"] == 16.0

    def test_return_td_counts_for_returning_team(self):
        # Returner is an offensive player on KC; TD credits KC DST
        df = _dst_df([{"position": "WR", "special_teams_tds": 1}])
        rows = build_dst_week_rows(df, self.PA)
        kc = [r for r in rows if r["team_abbr"] == "KC"][0]
        assert kc["dst_tds"] == 1

    def test_blocked_kick_credits_defense(self):
        # LV kicker got a FG blocked → KC DST gets the block
        df = _dst_df(
            [
                {"def_sacks": 1.0},  # ensures KC row exists
                {"position": "K", "team": "LV", "opponent_team": "KC", "fg_blocked": 1},
            ]
        )
        rows = build_dst_week_rows(df, self.PA)
        kc = [r for r in rows if r["team_abbr"] == "KC"][0]
        assert kc["dst_blocks"] == 1

    def test_skips_week_without_points_allowed(self):
        df = _dst_df([{"week": 9, "def_sacks": 1.0}])  # week 9 not in PA lookup
        rows = build_dst_week_rows(df, self.PA)
        assert rows == []

    def test_postseason_excluded(self):
        df = _dst_df([{"season_type": "POST", "def_sacks": 3.0}])
        assert build_dst_week_rows(df, self.PA) == []


# ── DST synthetic players (temp DB) ──────────────────────────────────────────


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


class TestEnsureDstPlayers:
    def test_creates_32_and_idempotent(self, tmp_db):
        created = ensure_dst_players(tmp_db, seasons=[2025])
        assert created == 32
        row = tmp_db.fetchone(
            "SELECT COUNT(*) AS n FROM players WHERE position = 'DST'", ()
        )
        assert row["n"] == 32
        entries = tmp_db.fetchone(
            "SELECT COUNT(*) AS n FROM roster_entries re "
            "JOIN players p ON p.player_id = re.player_id "
            "WHERE p.position = 'DST' AND re.season = 2025",
            (),
        )
        assert entries["n"] == 32
        # Second run: no duplicates
        ensure_dst_players(tmp_db, seasons=[2025])
        row2 = tmp_db.fetchone(
            "SELECT COUNT(*) AS n FROM players WHERE position = 'DST'", ()
        )
        assert row2["n"] == 32

    def test_dst_names_are_team_based(self, tmp_db):
        ensure_dst_players(tmp_db, seasons=[2025])
        row = tmp_db.fetchone(
            "SELECT full_name FROM players WHERE espn_id = 'DST-KC'", ()
        )
        assert row is not None
        assert "DST" in row["full_name"]


# ── Season aggregation for K/DST ─────────────────────────────────────────────


class TestAggregateSeasonStats:
    def test_sums_weekly_into_season(self, tmp_db):
        team = tmp_db.fetchone(
            "SELECT team_id FROM teams WHERE abbreviation = 'KC'", ()
        )
        cur = tmp_db.execute(
            "INSERT INTO players (espn_id, full_name, last_name, position) "
            "VALUES ('K-TEST', 'Test Kicker', 'Kicker', 'K')",
            (),
        )
        pid = cur.lastrowid
        for week, pts in ((1, 9.0), (2, 12.0), (3, 7.0)):
            tmp_db.upsert_player_weekly_stats(
                {
                    "player_id": pid,
                    "season": 2025,
                    "week": week,
                    "team_id": team["team_id"],
                    "position": "K",
                    "fantasy_points_ppr": pts,
                    "fantasy_points_standard": pts,
                }
            )
        tmp_db.commit()

        n = aggregate_kicker_dst_season_stats(tmp_db, [2025])
        assert n == 1
        row = tmp_db.fetchone(
            "SELECT games_played, fantasy_points_ppr, fantasy_points_standard "
            "FROM player_season_stats WHERE player_id = ? AND season = 2025",
            (pid,),
        )
        assert row["games_played"] == 3
        assert row["fantasy_points_ppr"] == 28.0
        assert row["fantasy_points_standard"] == 28.0


# ── New weekly-stats columns exist after migration ────────────────────────────


def test_weekly_stats_kicker_dst_columns(tmp_db):
    cols = {
        r["name"] for r in tmp_db.fetchall("PRAGMA table_info(player_weekly_stats)", ())
    }
    for c in (
        "fg_made_0_39",
        "fg_made_40_49",
        "fg_made_50_plus",
        "fg_missed",
        "xp_made",
        "xp_missed",
        "dst_sacks",
        "dst_interceptions",
        "dst_fumbles_recovered",
        "dst_tds",
        "dst_safeties",
        "dst_blocks",
        "dst_points_allowed",
    ):
        assert c in cols, f"missing column {c}"
