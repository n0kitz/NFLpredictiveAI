"""Tests for Phase 3 Lineup Optimizer (MILP via PuLP)."""

import pytest
from src.prediction.lineup_optimizer import (
    LineupPlayer,
    optimize_lineup,
    _correlation_bonus_map,
    players_from_projections,
    DFS_SLOTS,
    SEASON_LONG_SLOTS,
    _QB_STACK_BONUS,
    _BRING_BACK_BONUS,
    _RB_DEF_PENALTY,
)


def _make_player(pid, name, pos, team_id=1, team_abbr='KC', pts=10.0,
                 salary=5000, locked=False, excluded=False, opp_team=None):
    return LineupPlayer(
        player_id=pid,
        full_name=name,
        position=pos,
        team_id=team_id,
        team_abbr=team_abbr,
        projected_points=pts,
        salary=salary,
        is_locked=locked,
        is_excluded=excluded,
        opponent_team_id=opp_team,
    )


def _season_long_pool():
    """Minimal pool that satisfies SEASON_LONG_SLOTS (QB1 RB2 WR2 TE1 FLEX1 K1)."""
    players = []
    players.append(_make_player(1, 'QB1', 'QB', 1, 'KC', 25.0, 7000))
    players.append(_make_player(2, 'RB1', 'RB', 1, 'KC', 18.0, 6000))
    players.append(_make_player(3, 'RB2', 'RB', 2, 'SF', 16.0, 5500))
    players.append(_make_player(4, 'WR1', 'WR', 1, 'KC', 20.0, 6500))
    players.append(_make_player(5, 'WR2', 'WR', 3, 'DAL', 17.0, 5800))
    players.append(_make_player(6, 'WR3', 'WR', 2, 'SF', 15.0, 5000))
    players.append(_make_player(7, 'TE1', 'TE', 1, 'KC', 14.0, 5200))
    players.append(_make_player(8, 'K1', 'K', 4, 'BUF', 8.0, 4000))
    players.append(_make_player(9, 'RB3', 'RB', 3, 'DAL', 12.0, 4800))
    return players


# ── LineupPlayer construction ─────────────────────────────────────────────────

class TestLineupPlayer:
    def test_position_uppercased(self):
        p = _make_player(1, 'Test', 'qb')
        assert p.position == 'QB'

    def test_projected_points_float(self):
        p = _make_player(1, 'Test', 'RB', pts=15)
        assert isinstance(p.projected_points, float)

    def test_salary_int(self):
        p = _make_player(1, 'Test', 'WR', salary='6000')
        assert isinstance(p.salary, int)
        assert p.salary == 6000


# ── Correlation bonus map ─────────────────────────────────────────────────────

class TestCorrelationBonusMap:
    def test_qb_wr_same_team_gets_stack_bonus(self):
        qb = _make_player(1, 'QB', 'QB', team_id=1, opp_team=2)
        wr = _make_player(2, 'WR', 'WR', team_id=1)
        bonuses = _correlation_bonus_map([qb, wr])
        assert any(v == pytest.approx(_QB_STACK_BONUS) for v in bonuses.values())

    def test_qb_opp_wr_gets_bring_back_bonus(self):
        qb = _make_player(1, 'QB', 'QB', team_id=1, opp_team=2)
        wr = _make_player(2, 'OppWR', 'WR', team_id=2)
        bonuses = _correlation_bonus_map([qb, wr])
        assert any(v == pytest.approx(_BRING_BACK_BONUS) for v in bonuses.values())

    def test_rb_dst_same_team_penalty(self):
        rb  = _make_player(1, 'RB', 'RB',  team_id=1)
        dst = _make_player(2, 'DST', 'DST', team_id=1)
        bonuses = _correlation_bonus_map([rb, dst])
        assert any(v == pytest.approx(-_RB_DEF_PENALTY) for v in bonuses.values())

    def test_no_corr_for_unrelated_players(self):
        wr = _make_player(1, 'WR', 'WR', team_id=1)
        k  = _make_player(2, 'K', 'K',  team_id=2)
        bonuses = _correlation_bonus_map([wr, k])
        assert bonuses == {}


# ── optimize_lineup ───────────────────────────────────────────────────────────

class TestOptimizeLineup:
    def test_returns_one_lineup_basic(self):
        players = _season_long_pool()
        result = optimize_lineup(
            players,
            slots=SEASON_LONG_SLOTS,
            flex_positions={'RB', 'WR', 'TE'},
            salary_cap=None,
            n_lineups=1,
            correlations=False,
        )
        assert result['total_lineups'] == 1
        assert len(result['lineups']) == 1

    def test_lineup_respects_slot_counts(self):
        players = _season_long_pool()
        result = optimize_lineup(
            players,
            slots=SEASON_LONG_SLOTS,
            flex_positions={'RB', 'WR', 'TE'},
            n_lineups=1,
            correlations=False,
        )
        assert result['total_lineups'] == 1
        lu = result['lineups'][0]
        from collections import Counter
        slot_counts = Counter(p['slot'] for p in lu['players'])
        assert slot_counts['QB'] == SEASON_LONG_SLOTS['QB']
        assert slot_counts['RB'] == SEASON_LONG_SLOTS['RB']
        assert slot_counts['WR'] == SEASON_LONG_SLOTS['WR']
        assert slot_counts['TE'] == SEASON_LONG_SLOTS['TE']
        assert slot_counts['K'] == SEASON_LONG_SLOTS['K']
        assert slot_counts['FLEX'] == SEASON_LONG_SLOTS['FLEX']

    def test_salary_cap_enforced(self):
        players = _season_long_pool()
        cap = 46_000  # feasible (min combo ~41k)
        result = optimize_lineup(
            players,
            slots=SEASON_LONG_SLOTS,
            flex_positions={'RB', 'WR', 'TE'},
            salary_cap=cap,
            n_lineups=1,
            correlations=False,
        )
        assert result['total_lineups'] == 1
        lu = result['lineups'][0]
        assert lu['total_salary'] <= cap

    def test_excluded_player_not_in_lineup(self):
        players = _season_long_pool()
        players[0].is_excluded = True  # QB1
        result = optimize_lineup(
            players,
            slots=SEASON_LONG_SLOTS,
            flex_positions={'RB', 'WR', 'TE'},
            n_lineups=1,
            correlations=False,
        )
        # No lineup if only 1 QB and it's excluded
        assert result['total_lineups'] == 0

    def test_locked_player_in_lineup(self):
        players = _season_long_pool()
        players[7].is_locked = True  # K1 pid=8
        result = optimize_lineup(
            players,
            slots=SEASON_LONG_SLOTS,
            flex_positions={'RB', 'WR', 'TE'},
            n_lineups=1,
            correlations=False,
        )
        lu = result['lineups'][0]
        ids_in = [p['player_id'] for p in lu['players']]
        assert 8 in ids_in

    def test_multiple_lineups_differ(self):
        # Add extra players so 2 lineups are possible
        players = _season_long_pool()
        players.append(_make_player(10, 'QB2', 'QB', 5, 'BUF', 22.0, 6800))
        result = optimize_lineup(
            players,
            slots=SEASON_LONG_SLOTS,
            flex_positions={'RB', 'WR', 'TE'},
            n_lineups=2,
            correlations=False,
        )
        assert result['total_lineups'] == 2
        ids0 = frozenset(p['player_id'] for p in result['lineups'][0]['players'])
        ids1 = frozenset(p['player_id'] for p in result['lineups'][1]['players'])
        assert ids0 != ids1

    def test_exposure_computed(self):
        players = _season_long_pool()
        players.append(_make_player(10, 'QB2', 'QB', 5, 'BUF', 22.0, 6800))
        result = optimize_lineup(
            players,
            slots=SEASON_LONG_SLOTS,
            flex_positions={'RB', 'WR', 'TE'},
            n_lineups=2,
            correlations=False,
        )
        for pid, data in result['exposure'].items():
            assert 'count' in data
            assert 'pct' in data
            assert data['pct'] > 0

    def test_dfs_slots_constant_has_dk_and_fd(self):
        assert 'dk' in DFS_SLOTS
        assert 'fd' in DFS_SLOTS
        assert DFS_SLOTS['dk']['salary_cap'] == 50_000
        assert 'slots' in DFS_SLOTS['dk']

    def test_empty_pool_returns_empty(self):
        result = optimize_lineup(
            [],
            slots=SEASON_LONG_SLOTS,
            n_lineups=1,
        )
        assert result['total_lineups'] == 0
        assert result['lineups'] == []


# ── players_from_projections ──────────────────────────────────────────────────

class TestPlayersFromProjections:
    def _row(self, **kwargs):
        defaults = dict(
            player_id=1, full_name='Test', position='WR',
            team_id=1, team_abbr='KC', projected_points_ppr=12.5,
            headshot_url=None, opponent_team_id=None,
        )
        defaults.update(kwargs)
        return defaults

    def test_basic_conversion(self):
        rows = [self._row()]
        out = players_from_projections(rows)
        assert len(out) == 1
        assert out[0].position == 'WR'
        assert out[0].projected_points == pytest.approx(12.5)

    def test_unsupported_position_skipped(self):
        rows = [self._row(position='OL')]
        out = players_from_projections(rows)
        assert len(out) == 0

    def test_locked_and_excluded_flags(self):
        rows = [self._row(player_id=5), self._row(player_id=6)]
        out = players_from_projections(rows, locked_ids=[5], excluded_ids=[6])
        assert out[0].is_locked is True
        assert out[1].is_excluded is True
