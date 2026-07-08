"""Floors/ceilings from actual weekly scoring distributions (GUIDEBOOK 2.7).

floor_mult = p20(weekly points) / mean, ceiling_mult = p80 / mean —
computed alongside boom/bust from the same weekly rows, then applied
to the week's projection instead of the fixed ±25/35% placeholders.
"""

import pytest

from src.prediction.fantasy_scorer import (
    calc_boom_bust_from_rows,
    floor_ceiling_from_projection,
    percentile,
)


def _week(pts, snaps=50):
    return {'fantasy_points_ppr': pts, 'snaps': snaps, 'snap_pct': None}


class TestPercentile:
    def test_median_of_odd_list(self):
        assert percentile([1.0, 2.0, 3.0], 50) == pytest.approx(2.0)

    def test_interpolates_between_points(self):
        assert percentile([0.0, 10.0], 50) == pytest.approx(5.0)

    def test_p20_p80_of_uniform_run(self):
        pts = [float(x) for x in range(0, 11)]  # 0..10
        assert percentile(pts, 20) == pytest.approx(2.0)
        assert percentile(pts, 80) == pytest.approx(8.0)


class TestMultipliersFromWeeklyRows:
    def test_multipliers_present_with_enough_weeks(self):
        rows = [_week(p) for p in (5.0, 10.0, 15.0, 20.0, 25.0)]
        bb = calc_boom_bust_from_rows(rows)
        assert bb is not None
        assert 'floor_mult' in bb and 'ceiling_mult' in bb
        assert bb['floor_mult'] < 1.0 < bb['ceiling_mult']

    def test_steady_player_has_tight_band(self):
        steady = calc_boom_bust_from_rows([_week(p) for p in (12, 13, 12, 13, 12, 13)])
        volatile = calc_boom_bust_from_rows([_week(p) for p in (2, 25, 3, 28, 1, 24)])
        assert steady['floor_mult'] > volatile['floor_mult']
        assert steady['ceiling_mult'] < volatile['ceiling_mult']

    def test_floor_mult_never_negative(self):
        bb = calc_boom_bust_from_rows([_week(p) for p in (-2.0, 1.0, 30.0, 40.0, 50.0)])
        assert bb['floor_mult'] >= 0.0

    def test_under_four_weeks_returns_none(self):
        assert calc_boom_bust_from_rows([_week(10), _week(12), _week(14)]) is None


class TestFloorCeilingFromProjection:
    BB = {'floor_mult': 0.5, 'ceiling_mult': 1.6}

    def test_uses_distribution_multipliers(self):
        floor, ceiling = floor_ceiling_from_projection(10.0, self.BB, model_source='ml')
        assert floor == pytest.approx(5.0)
        assert ceiling == pytest.approx(16.0)

    def test_heuristic_with_history_gets_real_band(self):
        floor, ceiling = floor_ceiling_from_projection(10.0, self.BB, model_source='heuristic')
        assert floor == pytest.approx(5.0)
        assert ceiling == pytest.approx(16.0)

    def test_ml_without_history_falls_back_to_placeholder(self):
        floor, ceiling = floor_ceiling_from_projection(10.0, {}, model_source='ml')
        assert floor == pytest.approx(7.0)
        assert ceiling == pytest.approx(13.5)

    def test_heuristic_without_history_stays_none(self):
        floor, ceiling = floor_ceiling_from_projection(10.0, {}, model_source='heuristic')
        assert floor is None and ceiling is None

    def test_zero_projection_yields_none(self):
        floor, ceiling = floor_ceiling_from_projection(0.0, self.BB, model_source='ml')
        assert floor is None and ceiling is None
