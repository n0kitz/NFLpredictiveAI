"""
LeagueSettings — single source of truth for fantasy league configuration.

Encapsulates scoring format, league size (8-20 teams) and starting-roster
slots so replacement levels (VBD), tier boundaries and SQL points columns
derive from the actual league instead of hardcoded 12-team constants.

Defaults mirror a fantasy.nfl.com league: Standard scoring (no PPR),
10 teams, lineup QB/RB/RB/WR/WR/TE/FLEX/K/DST + 7 bench.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List

NFL_DEFAULT_SLOTS: Dict[str, int] = {
    'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1, 'K': 1, 'DST': 1, 'BN': 7,
}

VALID_SCORING = ('standard', 'ppr', 'half_ppr')

# How much of each FLEX slot each position typically absorbs league-wide.
_FLEX_WEIGHT: Dict[str, float] = {'RB': 0.45, 'WR': 0.45, 'TE': 0.10}

_VBD_POSITIONS = ('QB', 'RB', 'WR', 'TE', 'K', 'DST')


@dataclass(frozen=True)
class LeagueSettings:
    scoring: str = 'standard'
    league_size: int = 10
    roster_slots: Dict[str, int] = field(default_factory=lambda: dict(NFL_DEFAULT_SLOTS))

    def __post_init__(self) -> None:
        if self.scoring not in VALID_SCORING:
            raise ValueError(
                f"scoring must be one of {VALID_SCORING}, got {self.scoring!r}")
        if not 8 <= self.league_size <= 20:
            raise ValueError(
                f"league_size must be between 8 and 20, got {self.league_size}")

    def replacement_ranks(self) -> Dict[str, int]:
        """Positional rank at which a freely available replacement exists.

        replacement_rank(pos) = ceil(N * (starters[pos] + flex_weight * flex_slots))
        """
        flex_slots = self.roster_slots.get('FLEX', 0)
        ranks: Dict[str, int] = {}
        for pos in _VBD_POSITIONS:
            starters = self.roster_slots.get(pos, 0)
            flex_share = _FLEX_WEIGHT.get(pos, 0.0) * flex_slots
            ranks[pos] = math.ceil(self.league_size * (starters + flex_share))
        return ranks

    def tier_boundaries(self) -> List[int]:
        """Cumulative overall-rank cutoffs for draft tiers 1-8, scaled to size."""
        n = self.league_size
        return [n * m for m in (1, 3, 5, 7, 9, 11, 13, 15)]

    def points_expr(self, alias: str = 'pss') -> str:
        """SQL expression selecting fantasy points under this scoring format."""
        if self.scoring == 'ppr':
            return f'{alias}.fantasy_points_ppr'
        if self.scoring == 'half_ppr':
            return (f'(({alias}.fantasy_points_ppr + '
                    f'{alias}.fantasy_points_standard) / 2)')
        return f'{alias}.fantasy_points_standard'
