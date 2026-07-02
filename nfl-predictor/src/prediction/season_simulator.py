"""Monte Carlo rest-of-season simulator → playoff odds per team.

Completed games count as their actual results; every remaining game gets a win
probability from the prediction engine, predicted with cutoff_date = the game's
own date (the exact backtester recipe) so retro replays are leak-free.

Retro mode: pass as_of_week=N to treat all games after week N as unplayed and
re-simulate them — "playoff odds entering week N+1".

Simulated games update wins/losses and conference records but not point
differential (no scores are simulated); point diff from completed games remains
the third tiebreaker. Residual ties are broken by a per-simulation random
jitter, mirroring the NFL's coin flip for exhausted tiebreakers.
"""

import logging
import random
from typing import Any, Dict, List, Optional

from .standings import conference_seeding, finalize_win_pct

logger = logging.getLogger(__name__)

SEED_SLOTS = 7  # per conference: 4 division winners + 3 wildcards


def _week_int(week: Any) -> Optional[int]:
    try:
        return int(week)
    except (TypeError, ValueError):
        return None


def simulate_season(
    db,
    engine,
    season: int,
    as_of_week: Optional[int] = None,
    n_sims: int = 1000,
    seed: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Simulate the (rest of the) regular season n_sims times.

    Returns None when the season has no teams or no regular-season games.
    """
    teams = db.fetchall(
        """
        SELECT team_id, name, city, abbreviation, conference, division
        FROM teams
        WHERE (active_from IS NULL OR active_from <= ?)
          AND (active_until IS NULL OR active_until >= ?)
        """,
        (season, season),
    )
    if not teams:
        return None

    games = db.fetchall(
        """
        SELECT game_id, date, week, home_team_id, away_team_id,
               home_score, away_score, winner_id
        FROM games
        WHERE season = ? AND game_type = 'regular'
        ORDER BY date
        """,
        (season,),
    )
    if not games:
        return None

    info: Dict[int, dict] = {}
    base: Dict[int, dict] = {}
    for t in teams:
        tid = t["team_id"]
        info[tid] = {
            "abbr": t["abbreviation"],
            "name": f"{t['city']} {t['name']}",
            "conference": t["conference"],
            "division": f"{t['conference']} {t['division']}",
        }
        base[tid] = {
            "team_id": tid,
            "conference": t["conference"],
            "division": f"{t['conference']} {t['division']}",
            "wins": 0, "losses": 0, "ties": 0,
            "conf_wins": 0, "conf_losses": 0,
            "point_diff": 0,
        }

    completed: List[dict] = []
    remaining: List[dict] = []
    weeks_completed = 0
    for g in games:
        d = dict(g)
        if d["home_team_id"] not in base or d["away_team_id"] not in base:
            continue
        wi = _week_int(d["week"])
        played = d["home_score"] is not None
        counts_as_played = played and (as_of_week is None or (wi is not None and wi <= as_of_week))
        if counts_as_played:
            completed.append(d)
            if wi:
                weeks_completed = max(weeks_completed, wi)
        else:
            remaining.append(d)

    # Base records from completed games
    for g in completed:
        h, a = g["home_team_id"], g["away_team_id"]
        hs, as_ = base[h], base[a]
        hs["point_diff"] += g["home_score"] - g["away_score"]
        as_["point_diff"] += g["away_score"] - g["home_score"]
        if g["winner_id"] == h:
            hs["wins"] += 1; as_["losses"] += 1
        elif g["winner_id"] == a:
            as_["wins"] += 1; hs["losses"] += 1
        else:
            hs["ties"] += 1; as_["ties"] += 1
        if info[h]["conference"] == info[a]["conference"]:
            if g["winner_id"] == h:
                hs["conf_wins"] += 1; as_["conf_losses"] += 1
            elif g["winner_id"] == a:
                as_["conf_wins"] += 1; hs["conf_losses"] += 1

    # Engine win probabilities for every remaining game (cutoff = game date)
    matchups: List[tuple] = []
    for g in remaining:
        h, a = g["home_team_id"], g["away_team_id"]
        cutoff = str(g["date"])[:10] or None
        try:
            pred = engine.predict(
                home_team=info[h]["abbr"],
                away_team=info[a]["abbr"],
                apply_factors=False,
                current_season=season,
                cutoff_date=cutoff,
                is_playoff=False,
                week=g["week"],
                use_ml=False,
            )
            p_home = pred.home_win_probability
        except Exception as e:
            logger.warning("Simulator: prediction failed for game %s: %s", g["game_id"], e)
            p_home = 0.5
        same_conf = info[h]["conference"] == info[a]["conference"]
        matchups.append((h, a, p_home, same_conf))

    rng = random.Random(seed)
    acc = {
        tid: {"playoffs": 0, "division": 0, "wins_sum": 0.0, "seeds": [0] * (SEED_SLOTS + 1)}
        for tid in base
    }

    for _ in range(n_sims):
        sim = {tid: dict(rec) for tid, rec in base.items()}
        for h, a, p_home, same_conf in matchups:
            home_wins = rng.random() < p_home
            w, l = (h, a) if home_wins else (a, h)
            sim[w]["wins"] += 1
            sim[l]["losses"] += 1
            if same_conf:
                sim[w]["conf_wins"] += 1
                sim[l]["conf_losses"] += 1
        finalize_win_pct(sim)

        jitter = {tid: rng.random() for tid in sim}

        def sim_key(t: dict) -> tuple:
            return (
                t["win_pct"],
                t["conf_wins"] - t["conf_losses"],
                t["point_diff"],
                jitter[t["team_id"]],
            )

        for conf in ("AFC", "NFC"):
            leaders, others = conference_seeding(sim.values(), conf, sim_key)
            for t in leaders:
                acc[t["team_id"]]["division"] += 1
            seeds = leaders[:4] + others[:3]
            for seed_no, t in enumerate(seeds, start=1):
                acc[t["team_id"]]["playoffs"] += 1
                acc[t["team_id"]]["seeds"][seed_no] += 1

        for tid, t in sim.items():
            acc[tid]["wins_sum"] += t["wins"]

    def pct(count: int) -> float:
        return round(count / n_sims * 100, 1) if n_sims else 0.0

    team_rows = []
    for tid, a in acc.items():
        rec = base[tid]
        team_rows.append({
            "team_id": tid,
            "team_abbr": info[tid]["abbr"],
            "team_name": info[tid]["name"],
            "conference": info[tid]["conference"],
            "division": info[tid]["division"],
            "wins": rec["wins"], "losses": rec["losses"], "ties": rec["ties"],
            "mean_wins": round(a["wins_sum"] / n_sims, 1) if n_sims else 0.0,
            "playoff_pct": pct(a["playoffs"]),
            "division_pct": pct(a["division"]),
            "top_seed_pct": pct(a["seeds"][1]),
            "seed_distribution": {str(i): pct(a["seeds"][i]) for i in range(1, SEED_SLOTS + 1)},
        })
    team_rows.sort(key=lambda t: (-t["playoff_pct"], -t["mean_wins"], t["team_abbr"]))

    return {
        "season": season,
        "as_of_week": as_of_week,
        "weeks_completed": weeks_completed,
        "games_simulated": len(matchups),
        "n_sims": n_sims,
        "teams": team_rows,
    }
