"""Fantasy-related API endpoints."""

import json
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_db
from ..schemas import (
    FantasyPlayerEntry, FantasyLeaderboardResponse,
    FantasyProjectionEntry, StartSitResponse, StartSitPlayerEntry,
    DraftRankingEntry, TradeAnalysisResponse, TradePlayerEntry,
    FantasyRosterRequest, TradeAnalyzeRequest, ImportByNamesRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["fantasy"])


def _proj_row_to_entry(r, week: int, season: int) -> FantasyProjectionEntry:
    d = dict(r)
    contribs = []
    raw = d.get("contributions_json")
    if raw:
        try:
            contribs = json.loads(raw) or []
        except Exception as e:
            logger.warning("Failed to parse contributions_json: %s", e)
            contribs = []
    return FantasyProjectionEntry(
        player_id=d["player_id"],
        full_name=d.get("full_name", ""),
        position=d.get("position"),
        team_abbr=d.get("team_abbr"),
        headshot_url=d.get("headshot_url"),
        week=d.get("week", week),
        season=d.get("season", season),
        projected_points_ppr=d.get("projected_points_ppr") or 0.0,
        projected_points_std=d.get("projected_points_std") or 0.0,
        matchup_score=d.get("matchup_score") or 1.0,
        opportunity_score=d.get("opportunity_score") or 0.0,
        confidence=d.get("confidence") or "medium",
        injury_status=None,
        weather_impact=False,
        model_source=d.get("model_source") or "heuristic",
        model_version=d.get("model_version"),
        floor_ppr=d.get("floor_ppr"),
        ceiling_ppr=d.get("ceiling_ppr"),
        contributions=contribs,
    )


@router.get("/api/fantasy/model-info")
def get_fantasy_model_info():
    from ...prediction.player_ml_model import model_info
    return model_info()


@router.get("/api/fantasy/top", response_model=FantasyLeaderboardResponse)
def get_fantasy_top(
    position: Optional[str] = Query(None),
    season: int = Query(2024),
    scoring: str = Query("ppr"),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
):
    rows = db.get_fantasy_leaders(position, season, scoring, limit)
    players = [
        FantasyPlayerEntry(
            player_id=r["player_id"], full_name=r["full_name"],
            position=r["position"], team_abbr=r["team_abbr"], headshot_url=r["headshot_url"],
            games_played=r["games_played"] or 0,
            fantasy_points_ppr=r["fantasy_points_ppr"] or 0.0,
            fantasy_points_standard=r["fantasy_points_standard"] or 0.0,
            points_per_game_ppr=r["points_per_game_ppr"] or 0.0,
        )
        for r in rows
    ]
    return FantasyLeaderboardResponse(
        position=position.upper() if position else "ALL",
        season=season, scoring=scoring, players=players, count=len(players),
    )


@router.get("/api/fantasy/projections", response_model=List[FantasyProjectionEntry])
def get_fantasy_projections(
    week: int = Query(...),
    season: int = Query(2024),
    position: str = Query("all"),
    scoring: str = Query("ppr"),
    db=Depends(get_db),
):
    from ...prediction.fantasy_scorer import FantasyScorer
    rows = db.get_fantasy_projections(season, week, position, scoring)
    if not rows:
        scorer = FantasyScorer(db)
        scorer.generate_weekly_projections(season, week)
        rows = db.get_fantasy_projections(season, week, position, scoring)
    return [_proj_row_to_entry(r, week, season) for r in rows]


@router.get("/api/fantasy/start-sit", response_model=StartSitResponse)
def get_start_sit(
    player1_id: int = Query(...),
    player2_id: int = Query(...),
    week: int = Query(...),
    season: int = Query(2024),
    db=Depends(get_db),
):
    from ...prediction.fantasy_scorer import FantasyScorer
    scorer = FantasyScorer(db)
    result = scorer.start_sit_recommendation(player1_id, player2_id, week, season)
    if not result:
        raise HTTPException(status_code=404, detail="Could not generate recommendation")

    def _entry(d: dict) -> StartSitPlayerEntry:
        return StartSitPlayerEntry(
            player_id=d["player_id"], full_name=d["full_name"],
            position=d.get("position"), team_abbr=d.get("team_abbr"),
            headshot_url=d.get("headshot_url"),
            projected_points_ppr=d["projected_points_ppr"],
            matchup_score=d["matchup_score"], reasoning=d["reasoning"],
        )

    return StartSitResponse(
        start=_entry(result["start"]),
        sit=_entry(result["sit"]),
        confidence=result["confidence"],
    )


@router.get("/api/fantasy/waiver", response_model=List[FantasyProjectionEntry])
def get_waiver_wire(
    week: int = Query(...),
    season: int = Query(2024),
    scoring: str = Query("ppr"),
    position: str = Query("all"),
    limit: int = Query(30, ge=1, le=100),
    db=Depends(get_db),
):
    from ...prediction.fantasy_scorer import FantasyScorer
    rows = db.get_fantasy_projections(season, week, position, scoring)
    if not rows:
        scorer = FantasyScorer(db)
        scorer.generate_weekly_projections(season, week)
        rows = db.get_fantasy_projections(season, week, position, scoring)
    sorted_rows = sorted(rows, key=lambda r: float(r["opportunity_score"] or 0), reverse=True)
    return [_proj_row_to_entry(r, week, season) for r in sorted_rows[:limit]]


@router.get("/api/fantasy/draft-rankings", response_model=List[DraftRankingEntry])
def get_draft_rankings(
    season: int = Query(2025),
    scoring: str = Query("ppr"),
    position: str = Query("all"),
    db=Depends(get_db),
):
    from ...prediction.fantasy_scorer import FantasyScorer
    rows = db.get_draft_rankings(season, scoring, position)
    if not rows:
        scorer = FantasyScorer(db)
        scorer.generate_draft_rankings(season, scoring)
        rows = db.get_draft_rankings(season, scoring, position)
    return [
        DraftRankingEntry(
            player_id=r["player_id"], full_name=r.get("full_name", ""),
            position=r.get("position"), team_abbr=r.get("team_abbr"),
            headshot_url=r.get("headshot_url"),
            overall_rank=r["overall_rank"], position_rank=r["position_rank"],
            tier=r["tier"], adp=r["adp"],
            projected_season_points=r["projected_season_points"],
            season=r["season"], scoring_format=r["scoring_format"],
        )
        for r in rows
    ]


@router.post("/api/fantasy/roster")
def set_fantasy_roster(req: FantasyRosterRequest, db=Depends(get_db)):
    if len(req.player_ids) != len(req.slots):
        raise HTTPException(status_code=400, detail="player_ids and slots must have the same length")
    for pid, slot in zip(req.player_ids, req.slots):
        db.upsert_fantasy_roster({"league_id": req.league_id, "player_id": pid, "slot": slot})
    db.commit()
    roster = db.get_fantasy_roster(req.league_id)
    return {"league_id": req.league_id, "count": len(roster)}


@router.post("/api/fantasy/trade-analyze", response_model=TradeAnalysisResponse)
def analyze_trade(req: TradeAnalyzeRequest, db=Depends(get_db)):
    from ...prediction.fantasy_scorer import FantasyScorer
    scorer = FantasyScorer(db)
    result = scorer.analyze_trade(req.give_player_ids, req.get_player_ids, req.season, req.week)

    def _entry(d: dict) -> TradePlayerEntry:
        return TradePlayerEntry(
            player_id=d["player_id"], full_name=d["full_name"],
            position=d.get("position"), team_abbr=d.get("team_abbr"),
            headshot_url=d.get("headshot_url"), ros_projected=d["ros_projected"],
        )

    return TradeAnalysisResponse(
        give=[_entry(e) for e in result["give"]],
        get=[_entry(e) for e in result["get"]],
        give_total=result["give_total"], get_total=result["get_total"],
        verdict=result["verdict"], delta=result["delta"],
    )


@router.get("/api/fantasy/power-rankings")
def get_power_rankings(
    week: int = Query(...),
    season: int = Query(2024),
    db=Depends(get_db),
):
    def _compute(target_week: int) -> dict:
        teams = db.fetchall(
            """
            SELECT team_id, name, city, abbreviation, conference
            FROM teams WHERE (active_from IS NULL OR active_from <= ?)
              AND (active_until IS NULL OR active_until >= ?)
            """,
            (season, season),
        )
        scored = []
        for t in teams:
            tid = t["team_id"]
            recent = db.fetchall(
                """
                SELECT home_team_id, away_team_id, home_score, away_score, winner_id
                FROM games WHERE season=? AND game_type='regular'
                  AND (home_team_id=? OR away_team_id=?) AND home_score IS NOT NULL
                  AND CAST(week AS INTEGER) < ?
                ORDER BY date DESC LIMIT 4
                """,
                (season, tid, tid, target_week),
            )
            wins = sum(1 for g in recent if g["winner_id"] == tid)
            form = wins / max(len(recent), 1) if recent else 0.5
            pt_diff = sum(
                (g["home_score"] or 0) - (g["away_score"] or 0) if g["home_team_id"] == tid
                else (g["away_score"] or 0) - (g["home_score"] or 0)
                for g in recent
            )
            pt_norm = max(-1.0, min(1.0, pt_diff / 60.0))

            adv = db.fetchone(
                "SELECT yards_per_play FROM team_advanced_stats WHERE team_id=? AND season=?",
                (tid, season),
            ) or db.fetchone(
                "SELECT yards_per_play FROM team_advanced_stats WHERE team_id=? ORDER BY season DESC LIMIT 1",
                (tid,),
            )
            adv_score = 0.5
            if adv and adv["yards_per_play"]:
                adv_score = min(1.0, max(0.0, (float(adv["yards_per_play"]) - 3.5) / 3.5))

            nxt = db.fetchone(
                """
                SELECT home_team_id, away_team_id FROM games
                WHERE season=? AND (home_team_id=? OR away_team_id=?)
                  AND CAST(week AS INTEGER) >= ? AND home_score IS NULL
                ORDER BY date ASC LIMIT 1
                """,
                (season, tid, tid, target_week),
            )
            opp_str = 0.5
            if nxt:
                opp_id = nxt["away_team_id"] if nxt["home_team_id"] == tid else nxt["home_team_id"]
                opp_r = db.fetchall(
                    """
                    SELECT winner_id FROM games WHERE season=? AND game_type='regular'
                      AND (home_team_id=? OR away_team_id=?) AND home_score IS NOT NULL
                    ORDER BY date DESC LIMIT 4
                    """,
                    (season, opp_id, opp_id),
                )
                if opp_r:
                    opp_str = sum(1 for g in opp_r if g["winner_id"] == opp_id) / len(opp_r)

            composite = 0.40 * form + 0.20 * ((pt_norm + 1) / 2) + 0.20 * (1.0 - opp_str) + 0.20 * adv_score
            scored.append({
                "team_id": tid, "team_abbr": t["abbreviation"],
                "team_name": f"{t['city']} {t['name']}",
                "conference": t["conference"], "composite": composite,
                "recent_wins": wins, "recent_games": len(recent), "pt_diff_4g": pt_diff,
            })

        scored.sort(key=lambda x: x["composite"], reverse=True)
        return {s["team_id"]: {**s, "rank": i + 1} for i, s in enumerate(scored)}

    current = _compute(week)
    prev = _compute(max(1, week - 1)) if week > 1 else {}

    result = []
    for tid, data in sorted(current.items(), key=lambda x: x[1]["rank"]):
        rank = data["rank"]
        rank_change = (prev[tid]["rank"] - rank) if (prev and tid in prev) else 0
        trend = "rising" if rank_change > 3 else "falling" if rank_change < -3 else "neutral"
        if rank <= 5:
            implication = "Strong offense — start their skill players"
        elif rank >= 28:
            implication = "Weak defense — target opposing players"
        elif trend == "rising":
            implication = "Trending up — matchup-based starts"
        elif trend == "falling":
            implication = "Struggling recently — proceed with caution"
        else:
            implication = "Mid-tier team — rely on matchup"

        result.append({
            "rank": rank, "rank_change": rank_change, "trend": trend,
            "team_abbr": data["team_abbr"], "team_name": data["team_name"],
            "conference": data["conference"],
            "composite_score": round(data["composite"], 3),
            "recent_wins": data["recent_wins"], "recent_games": data["recent_games"],
            "pt_diff_4g": data["pt_diff_4g"], "implication": implication,
        })

    return {"week": week, "season": season, "rankings": result}


@router.post("/api/fantasy/roster/import-by-names")
def import_roster_by_names(req: ImportByNamesRequest, db=Depends(get_db)):
    matched, unmatched = [], []
    for raw in req.names:
        name = raw.strip()
        if not name:
            continue
        rows = db.fetchall(
            """
            SELECT p.player_id, p.full_name, p.position, t.abbreviation AS team_abbr
            FROM players p
            LEFT JOIN roster_entries re ON re.player_id = p.player_id AND re.season = ?
            LEFT JOIN teams t ON t.team_id = re.team_id
            WHERE LOWER(p.full_name) LIKE LOWER(?) ORDER BY re.season DESC LIMIT 1
            """,
            (req.season, f"%{name}%"),
        )
        if not rows:
            last = name.split()[-1]
            rows = db.fetchall(
                """
                SELECT p.player_id, p.full_name, p.position, t.abbreviation AS team_abbr
                FROM players p
                LEFT JOIN roster_entries re ON re.player_id = p.player_id AND re.season = ?
                LEFT JOIN teams t ON t.team_id = re.team_id
                WHERE LOWER(p.full_name) LIKE LOWER(?) ORDER BY re.season DESC LIMIT 1
                """,
                (req.season, f"%{last}%"),
            )
        if rows:
            r = rows[0]
            matched.append({
                "input_name": name, "player_id": r["player_id"],
                "full_name": r["full_name"], "position": r["position"], "team_abbr": r["team_abbr"],
            })
        else:
            unmatched.append(name)
    return {"matched": matched, "unmatched": unmatched}


@router.get("/api/fantasy/trade-values")
def get_trade_values(week: int = Query(...), season: int = Query(2024), db=Depends(get_db)):
    rows = db.fetchall(
        """
        SELECT fp.player_id, p.full_name, p.position, p.headshot_url,
               t.abbreviation AS team_abbr,
               SUM(fp.projected_points_ppr) AS ros_projected,
               AVG(fp.matchup_score) AS avg_matchup_score,
               COUNT(*) AS weeks_remaining
        FROM fantasy_projections fp
        JOIN players p ON p.player_id = fp.player_id
        LEFT JOIN roster_entries re ON re.player_id = fp.player_id AND re.season = fp.season
        LEFT JOIN teams t ON t.team_id = re.team_id
        WHERE fp.season = ? AND fp.week >= ?
        GROUP BY fp.player_id, p.full_name, p.position, p.headshot_url, t.abbreviation
        ORDER BY ros_projected DESC LIMIT 100
        """,
        (season, week),
    )
    result = []
    for i, r in enumerate(rows, start=1):
        avg_ms = float(r["avg_matchup_score"] or 1.0)
        result.append({
            "rank": i, "player_id": r["player_id"], "full_name": r["full_name"],
            "position": r["position"], "team_abbr": r["team_abbr"], "headshot_url": r["headshot_url"],
            "ros_projected": round(float(r["ros_projected"] or 0), 1),
            "avg_matchup_score": round(avg_ms, 3),
            "weeks_remaining": r["weeks_remaining"],
            "schedule_difficulty": "easy" if avg_ms >= 1.1 else "hard" if avg_ms <= 0.9 else "neutral",
        })
    return {"week": week, "season": season, "players": result, "count": len(result)}
