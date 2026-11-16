"""Save a pick for every game of the upcoming week.

Predictions are graded only by games played after they were made (see
``Database.enrich_prediction_history``), so the self-graded ledger behind
``/history`` grows solely from picks saved before kickoff. The weekly cron
calls this so that happens without anyone clicking through the UI.
"""

import logging
from datetime import date
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# A cron pick saved this recently for the same pairing is this week's already.
_DEDUP_DAYS = 6


def save_upcoming_picks(
    db: Any, engine: Any, season: int, week: int, today: Optional[date] = None
) -> Dict[str, int]:
    """Predict and store each not-yet-started game of ``season``/``week``.

    Uses the engine exactly as the backtester does -- weighted-sum model, no
    game factors -- so the ledger measures the configuration whose accuracy is
    published, and no Vegas/injury/weather context can leak in.

    Games dated before ``today`` are skipped even without a score: they have
    kicked off, and a result that merely hasn't been imported yet must not be
    "predicted". Re-running within the week does not duplicate picks; manual
    picks are ignored for that check, the cron's pick is the ledger's.

    Returns counts: ``saved``, ``skipped`` (already picked), ``failed``.
    """
    today = today or date.today()
    games = db.fetchall(
        """
        SELECT g.game_id, g.home_team_id, g.away_team_id,
               ht.abbreviation AS home_abbr, at.abbreviation AS away_abbr
        FROM games g
        JOIN teams ht ON ht.team_id = g.home_team_id
        JOIN teams at ON at.team_id = g.away_team_id
        WHERE g.season = ? AND CAST(g.week AS INTEGER) = ? AND g.game_type = 'regular'
          AND g.home_score IS NULL AND g.date >= ?
        ORDER BY g.date, g.game_id
        """,
        (season, week, str(today)),
    )

    result = {"saved": 0, "skipped": 0, "failed": 0}
    for g in games:
        already = db.fetchone(
            "SELECT 1 FROM prediction_history "
            "WHERE home_team_id = ? AND away_team_id = ? AND correct IS NULL "
            "AND source = 'cron' AND date(predicted_at) >= date(?, ?)",
            (g["home_team_id"], g["away_team_id"], str(today), f"-{_DEDUP_DAYS} days"),
        )
        if already:
            result["skipped"] += 1
            continue
        try:
            p = engine.predict(
                home_team=g["home_abbr"],
                away_team=g["away_abbr"],
                apply_factors=False,
                current_season=season,
                week=week,
            )
            home_wins = p.home_win_probability > p.away_win_probability
            db.insert_prediction(
                home_team_id=p.home_team_id,
                away_team_id=p.away_team_id,
                predicted_winner_id=p.home_team_id if home_wins else p.away_team_id,
                home_prob=round(p.home_win_probability, 4),
                away_prob=round(p.away_win_probability, 4),
                confidence=p.confidence,
                source="cron",
            )
            result["saved"] += 1
        except Exception as e:
            logger.warning(
                "Pick failed for %s @ %s: %s", g["away_abbr"], g["home_abbr"], e
            )
            result["failed"] += 1
    db.commit()
    return result
