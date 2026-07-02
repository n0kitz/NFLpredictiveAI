"""Shared standings/seeding logic.

Used by both the playoff-picture endpoint and the Monte Carlo season simulator
so seeding rules can never drift between the two.

Seeding model (simplified NFL format): 4 division winners are seeds 1-4,
ordered by record; the 3 best non-winners are wildcard seeds 5-7.
Tiebreak: win% → conference win differential → point differential.
"""

from typing import Callable, Dict, Iterable, List, Tuple


def default_sort_key(t: dict) -> tuple:
    return (t["win_pct"], t["conf_wins"] - t["conf_losses"], t["point_diff"])


def finalize_win_pct(stats: Dict[int, dict]) -> None:
    """Compute win_pct in place (ties count half)."""
    for s in stats.values():
        total = s["wins"] + s["losses"] + s["ties"]
        s["win_pct"] = (s["wins"] + s["ties"] * 0.5) / total if total > 0 else 0.0


def conference_seeding(
    stats_values: Iterable[dict],
    conference: str,
    sort_key: Callable[[dict], tuple] = default_sort_key,
) -> Tuple[List[dict], List[dict]]:
    """Return (division_leaders, non_leaders), each sorted best-first.

    Division leaders are seeds 1-4; the first three non-leaders are the
    wildcard seeds 5-7.
    """
    conf_teams = [s for s in stats_values if s["conference"] == conference]
    divisions = sorted(set(s["division"] for s in conf_teams))
    leaders: List[dict] = []
    non_leaders: List[dict] = []
    for div in divisions:
        div_teams = sorted(
            (s for s in conf_teams if s["division"] == div),
            key=sort_key, reverse=True,
        )
        if div_teams:
            leaders.append(div_teams[0])
            non_leaders.extend(div_teams[1:])
    leaders.sort(key=sort_key, reverse=True)
    non_leaders.sort(key=sort_key, reverse=True)
    return leaders, non_leaders
