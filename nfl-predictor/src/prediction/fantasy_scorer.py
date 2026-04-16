"""Fantasy Football scorer: projections, matchup scoring, draft rankings, trade analysis."""

import logging
import random
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# League average baselines (used to normalise matchup score around 1.0)
_AVG_YPP = 5.5
_AVG_SACK_RATE = 0.07
_AVG_RZ_EFF = 0.15

# Injury status → (points_multiplier, confidence_label)
_INJURY_RULES: Dict[str, tuple] = {
    'Out':          (0.0, 'high'),
    'IR':           (0.0, 'high'),
    'PUP':          (0.0, 'high'),
    'Doubtful':     (0.2, 'low'),
    'Questionable': (0.7, 'low'),
}

_FANTASY_POSITIONS = ('QB', 'RB', 'WR', 'TE', 'K')

# Tier boundaries (cumulative player count thresholds)
_TIER_BOUNDARIES = [12, 36, 60, 84, 108, 132, 156, 180]


class FantasyScorer:
    """Generate fantasy projections, draft rankings, trade analysis, and start/sit advice."""

    def __init__(self, db) -> None:
        self.db = db

    # ── Matchup scoring ──────────────────────────────────────────────────────

    def calculate_matchup_score(
        self,
        player_id: int,
        opponent_team_id: int,
        position: str,
        season: int,
    ) -> float:
        """
        Return a matchup score in [0.7, 1.3] (1.0 = league-average opponent).

        Uses the opponent's team_advanced_stats as a proxy for defensive quality.
        Falls back to prior season data or 1.0 if no stats are available.
        """
        stats = self.db.get_advanced_stats(opponent_team_id, season)
        if not stats:
            stats = self.db.get_advanced_stats(opponent_team_id, season - 1)
        if not stats:
            return 1.0

        pos = (position or '').upper()
        ypp = float(stats['yards_per_play'] or _AVG_YPP)
        sack_rate = float(stats['sack_rate_allowed'] or _AVG_SACK_RATE)
        rz_eff = float(stats['redzone_efficiency'] or _AVG_RZ_EFF)

        if pos == 'QB':
            # Opponent takes more sacks → weaker team overall → better matchup
            sack_factor = sack_rate / _AVG_SACK_RATE
            ypp_factor = ypp / _AVG_YPP
            raw = sack_factor * 0.5 + ypp_factor * 0.5
        elif pos in ('RB', 'FB'):
            raw = ypp / _AVG_YPP
        else:  # WR, TE, K, other
            rz_factor = 1.0 + (rz_eff - _AVG_RZ_EFF)
            ypp_factor = ypp / _AVG_YPP
            raw = rz_factor * 0.4 + ypp_factor * 0.6

        return round(max(0.7, min(1.3, raw)), 3)

    # ── Single-player projection ─────────────────────────────────────────────

    def calculate_projection(
        self,
        player_id: int,
        week: int,
        season: int,
        opponent_team_id: Optional[int],
    ) -> Dict[str, Any]:
        """
        Project fantasy points for a player for a given week.

        Applies matchup, injury, weather, and over/under adjustments.
        Returns an empty dict if the player is not found.
        """
        player = self.db.get_player_by_id(player_id)
        if not player:
            return {}

        name = player['full_name']
        pos = (player['position'] or '').upper()

        # Base: average weekly points from the most relevant season stats
        stats = self.db.get_player_stats(player_id, season)
        if not stats:
            stats = self.db.get_player_stats(player_id)  # most recent season

        if stats and stats['games_played'] and stats['games_played'] > 0:
            base_ppr = float(stats['fantasy_points_ppr'] or 0) / stats['games_played']
            base_std = float(stats['fantasy_points_standard'] or 0) / stats['games_played']
        else:
            base_ppr = 0.0
            base_std = 0.0

        matchup_score = 1.0
        if opponent_team_id:
            matchup_score = self.calculate_matchup_score(
                player_id, opponent_team_id, pos, season
            )

        proj_ppr = base_ppr * matchup_score
        proj_std = base_std * matchup_score
        confidence = 'medium'
        injury_status: Optional[str] = None
        weather_impact = False

        # Injury adjustment
        inj = self._get_injury_for_player(name)
        if inj:
            status = inj['injury_status']
            injury_status = status
            if status in _INJURY_RULES:
                mult, conf = _INJURY_RULES[status]
                proj_ppr *= mult
                proj_std *= mult
                confidence = conf

        # Weather adjustment for outdoor skill positions
        if opponent_team_id and pos in ('QB', 'WR', 'TE'):
            wx = self._get_weather_for_matchup(opponent_team_id, season, week)
            if wx and not wx['is_dome']:
                if float(wx['precipitation_mm'] or 0) > 0:
                    proj_ppr *= 0.93
                    proj_std *= 0.93
                    weather_impact = True

        # Over/under scaling for skill positions (neutral O/U ≈ 44)
        if opponent_team_id and pos in ('QB', 'WR', 'TE', 'RB'):
            ou = self._get_over_under(opponent_team_id, season, week)
            if ou and ou > 0:
                ou_factor = max(0.9, min(1.1, ou / 44.0))
                proj_ppr *= ou_factor
                proj_std *= ou_factor

        return {
            'player_id':            player_id,
            'full_name':            name,
            'position':             pos,
            'projected_points_ppr': round(proj_ppr, 2),
            'projected_points_std': round(proj_std, 2),
            'matchup_score':        matchup_score,
            'confidence':           confidence,
            'injury_status':        injury_status,
            'weather_impact':       weather_impact,
        }

    # ── Opportunity score ────────────────────────────────────────────────────

    def calculate_opportunity_score(
        self,
        player_id: int,
        week: int,
        season: int,
        opponent_team_id: Optional[int],
    ) -> float:
        """
        Score 0–10 representing usage opportunity this week.

        Weighted: 0.4 × targets_per_game + 0.3 × snap_pct_proxy + 0.3 × matchup_score.
        """
        stats = self.db.get_player_stats(player_id, season)
        player = self.db.get_player_by_id(player_id)
        if not stats or not stats['games_played'] or not player:
            return 0.0

        gp = stats['games_played']
        pos = (player['position'] or '').upper()

        targets_per_game = float(stats['targets'] or 0) / gp
        snap_pct_proxy = 0.8 if self._is_starter(player_id, season) else 0.4

        matchup = 1.0
        if opponent_team_id:
            matchup = self.calculate_matchup_score(
                player_id, opponent_team_id, pos, season
            )

        # Normalise to 0–10; targets/game typically 0–12 → divide by 1.2
        tpg_norm = min(targets_per_game / 1.2, 10.0)
        snap_norm = snap_pct_proxy * 10.0
        match_norm = (matchup - 0.7) / 0.6 * 10.0  # 0.7→0, 1.3→10

        score = 0.4 * tpg_norm + 0.3 * snap_norm + 0.3 * match_norm
        return round(min(10.0, max(0.0, score)), 2)

    # ── Weekly projections (batch) ───────────────────────────────────────────

    def generate_weekly_projections(self, season: int, week: int) -> List[Dict[str, Any]]:
        """
        Generate and persist projections for all active skill-position players.

        Queries all players in QB/RB/WR/TE/K who have a roster entry for the season,
        finds their opponent for the week, calls calculate_projection, and upserts
        results into fantasy_projections. Returns the full list of projection dicts.
        """
        rows = self.db.fetchall(
            """
            SELECT DISTINCT p.player_id, p.position, re.team_id
            FROM players p
            JOIN roster_entries re ON re.player_id = p.player_id
            WHERE p.position IN ('QB','RB','WR','TE','K')
              AND re.season = ?
            """,
            (season,),
        )

        results: List[Dict[str, Any]] = []

        for row in rows:
            player_id = row['player_id']
            team_id = row['team_id']

            # Find the game for this team in the given week
            game = self.db.fetchone(
                """
                SELECT game_id, home_team_id, away_team_id
                FROM games
                WHERE season = ?
                  AND (CAST(week AS INTEGER) = ? OR week = CAST(? AS TEXT))
                  AND (home_team_id = ? OR away_team_id = ?)
                LIMIT 1
                """,
                (season, week, str(week), team_id, team_id),
            )

            opponent_team_id: Optional[int] = None
            if game:
                opponent_team_id = (
                    game['away_team_id']
                    if game['home_team_id'] == team_id
                    else game['home_team_id']
                )

            proj = self.calculate_projection(player_id, week, season, opponent_team_id)
            if not proj:
                continue

            opp_score = self.calculate_opportunity_score(
                player_id, week, season, opponent_team_id
            )
            proj['opportunity_score'] = opp_score
            proj['week'] = week
            proj['season'] = season
            proj['opponent_team_id'] = opponent_team_id

            team_row = self.db.fetchone(
                "SELECT abbreviation FROM teams WHERE team_id=?", (team_id,)
            )
            proj['team_abbr'] = team_row['abbreviation'] if team_row else None

            player_obj = self.db.get_player_by_id(player_id)
            proj['headshot_url'] = player_obj['headshot_url'] if player_obj else None

            self.db.upsert_fantasy_projection({
                'player_id':            player_id,
                'season':               season,
                'week':                 week,
                'opponent_team_id':     opponent_team_id,
                'projected_points_ppr': proj['projected_points_ppr'],
                'projected_points_std': proj['projected_points_std'],
                'matchup_score':        proj['matchup_score'],
                'opportunity_score':    opp_score,
                'confidence':           proj['confidence'],
            })

            results.append(proj)

        self.db.commit()
        logger.info(
            "Generated %d projections for season %s week %s", len(results), season, week
        )
        return results

    # ── Draft rankings ───────────────────────────────────────────────────────

    def generate_draft_rankings(self, season: int, scoring_format: str) -> List[Dict[str, Any]]:
        """
        Generate and persist draft rankings for a given season and scoring format.

        Base score: previous season fantasy points. Adjusts for player age (>30)
        and injury frequency. Assigns tiers, position ranks, and ADP (rank + gaussian σ=2).
        Returns a sorted list of ranking dicts.
        """
        prev_season = season - 1
        pts_col = 'fantasy_points_ppr' if scoring_format == 'ppr' else 'fantasy_points_standard'

        rows = self.db.fetchall(
            f"""
            SELECT p.player_id, p.full_name, p.position, p.headshot_url,
                   p.date_of_birth, p.experience_years,
                   t.abbreviation AS team_abbr,
                   COALESCE(pss.{pts_col}, 0) AS season_pts,
                   COALESCE(pss.games_played, 0) AS games_played
            FROM players p
            JOIN roster_entries re ON re.player_id = p.player_id AND re.season = ?
            LEFT JOIN player_season_stats pss
                ON pss.player_id = p.player_id AND pss.season = ?
            LEFT JOIN teams t ON t.team_id = re.team_id
            WHERE p.position IN ('QB','RB','WR','TE','K')
            GROUP BY p.player_id
            ORDER BY season_pts DESC
            """,
            (season, prev_season),
        )

        if not rows:
            # Fall back to any available season stats
            rows = self.db.fetchall(
                f"""
                SELECT p.player_id, p.full_name, p.position, p.headshot_url,
                       p.date_of_birth, p.experience_years,
                       t.abbreviation AS team_abbr,
                       COALESCE(pss.{pts_col}, 0) AS season_pts,
                       COALESCE(pss.games_played, 0) AS games_played
                FROM players p
                JOIN roster_entries re ON re.player_id = p.player_id AND re.season = ?
                LEFT JOIN player_season_stats pss ON pss.player_id = p.player_id
                LEFT JOIN teams t ON t.team_id = re.team_id
                WHERE p.position IN ('QB','RB','WR','TE','K')
                GROUP BY p.player_id
                ORDER BY season_pts DESC
                """,
                (season,),
            )

        # Compute adjusted scores
        scored: List[Dict[str, Any]] = []
        for r in rows:
            score = float(r['season_pts'] or 0)

            # Age penalty: −2 % per year above 30
            dob = r['date_of_birth']
            if dob:
                try:
                    age = season - int(str(dob)[:4])
                    if age > 30:
                        score *= max(0.7, 1.0 - 0.02 * (age - 30))
                except (ValueError, TypeError):
                    pass

            # Injury-frequency penalty: −5 % per report beyond 2
            inj_count = self._get_injury_frequency(r['full_name'])
            if inj_count > 2:
                score *= max(0.8, 1.0 - 0.05 * (inj_count - 2))

            scored.append({
                'player_id':  r['player_id'],
                'full_name':  r['full_name'],
                'position':   r['position'],
                'headshot_url': r['headshot_url'],
                'team_abbr':  r['team_abbr'],
                'adj_score':  score,
                'season_pts': float(r['season_pts'] or 0),
            })

        scored.sort(key=lambda x: x['adj_score'], reverse=True)

        pos_rank_counter: Dict[str, int] = {}
        results: List[Dict[str, Any]] = []

        for overall_rank, entry in enumerate(scored, start=1):
            pos = entry['position'] or 'OTH'
            pos_rank_counter[pos] = pos_rank_counter.get(pos, 0) + 1
            pos_rank = pos_rank_counter[pos]

            tier = len(_TIER_BOUNDARIES)
            for i, boundary in enumerate(_TIER_BOUNDARIES, start=1):
                if overall_rank <= boundary:
                    tier = i
                    break

            adp = round(max(1.0, overall_rank + random.gauss(0, 2)), 1)

            ranking: Dict[str, Any] = {
                'player_id':               entry['player_id'],
                'full_name':               entry['full_name'],
                'position':                entry['position'],
                'headshot_url':            entry['headshot_url'],
                'team_abbr':               entry['team_abbr'],
                'overall_rank':            overall_rank,
                'position_rank':           pos_rank,
                'tier':                    tier,
                'adp':                     adp,
                'projected_season_points': round(entry['season_pts'], 1),
                'season':                  season,
                'scoring_format':          scoring_format,
            }
            results.append(ranking)

            self.db.upsert_draft_ranking({
                'season':                  season,
                'scoring_format':          scoring_format,
                'player_id':               entry['player_id'],
                'overall_rank':            overall_rank,
                'position_rank':           pos_rank,
                'tier':                    tier,
                'adp':                     adp,
                'projected_season_points': round(entry['season_pts'], 1),
            })

        self.db.commit()
        logger.info(
            "Generated %d draft rankings for %s %s", len(results), season, scoring_format
        )
        return results

    # ── Trade analysis ───────────────────────────────────────────────────────

    def analyze_trade(
        self,
        give_player_ids: List[int],
        get_player_ids: List[int],
        season: int,
        current_week: int,
    ) -> Dict[str, Any]:
        """
        Compare rest-of-season (ROS) projected points for two sets of players.

        Verdict: 'WIN' if get_total > give_total × 1.05, 'LOSE' if inverse, else 'FAIR'.
        """
        remaining_weeks = list(range(current_week, 19))

        def ros_points(pid: int) -> float:
            return round(
                sum(
                    self.calculate_projection(pid, wk, season, None).get(
                        'projected_points_ppr', 0.0
                    )
                    for wk in remaining_weeks
                ),
                1,
            )

        def build_entry(pid: int, ros: float) -> Dict[str, Any]:
            p = self.db.get_player_by_id(pid)
            if not p:
                return {
                    'player_id': pid, 'full_name': 'Unknown', 'ros_projected': ros,
                    'position': None, 'team_abbr': None, 'headshot_url': None,
                }
            team_row = self.db.fetchone(
                """
                SELECT t.abbreviation FROM teams t
                JOIN roster_entries re ON re.team_id = t.team_id
                WHERE re.player_id = ?
                ORDER BY re.season DESC LIMIT 1
                """,
                (pid,),
            )
            return {
                'player_id':   pid,
                'full_name':   p['full_name'],
                'position':    p['position'],
                'team_abbr':   team_row['abbreviation'] if team_row else None,
                'headshot_url': p['headshot_url'],
                'ros_projected': ros,
            }

        give_entries = [build_entry(pid, ros_points(pid)) for pid in give_player_ids]
        get_entries  = [build_entry(pid, ros_points(pid)) for pid in get_player_ids]

        give_total = round(sum(e['ros_projected'] for e in give_entries), 1)
        get_total  = round(sum(e['ros_projected'] for e in get_entries), 1)
        delta      = round(get_total - give_total, 1)

        if get_total > give_total * 1.05:
            verdict = 'WIN'
        elif give_total > get_total * 1.05:
            verdict = 'LOSE'
        else:
            verdict = 'FAIR'

        return {
            'give':       give_entries,
            'get':        get_entries,
            'give_total': give_total,
            'get_total':  get_total,
            'verdict':    verdict,
            'delta':      delta,
        }

    # ── Start / Sit recommendation ───────────────────────────────────────────

    def start_sit_recommendation(
        self,
        player1_id: int,
        player2_id: int,
        week: int,
        season: int,
    ) -> Dict[str, Any]:
        """
        Compare two players and recommend which to start for the given week.

        Returns a dict with 'start', 'sit' (each a full projection dict + reasoning),
        and 'confidence'.
        """
        p1 = self.calculate_projection(player1_id, week, season, None)
        p2 = self.calculate_projection(player2_id, week, season, None)

        def _enrich(proj: Dict, pid: int) -> Dict:
            player = self.db.get_player_by_id(pid)
            if player:
                proj.setdefault('full_name', player['full_name'])
                proj['headshot_url'] = player['headshot_url']
            team_row = self.db.fetchone(
                """
                SELECT t.abbreviation FROM teams t
                JOIN roster_entries re ON re.team_id = t.team_id
                WHERE re.player_id = ?
                ORDER BY re.season DESC LIMIT 1
                """,
                (pid,),
            )
            proj['team_abbr'] = team_row['abbreviation'] if team_row else None
            return proj

        p1 = _enrich(p1, player1_id)
        p2 = _enrich(p2, player2_id)

        if p1.get('projected_points_ppr', 0) >= p2.get('projected_points_ppr', 0):
            start_proj, sit_proj = p1, p2
            start_id, sit_id = player1_id, player2_id
        else:
            start_proj, sit_proj = p2, p1
            start_id, sit_id = player2_id, player1_id

        def _reasoning(proj: Dict, is_start: bool) -> str:
            inj = proj.get('injury_status')
            if inj in ('Out', 'IR', 'PUP'):
                return f"Ruled out ({inj}) — do not start."
            if inj == 'Doubtful':
                return "Doubtful to play — avoid if possible."
            ms = proj.get('matchup_score', 1.0)
            pts = proj.get('projected_points_ppr', 0.0)
            parts = []
            if is_start:
                parts.append(
                    f"Favorable matchup (score {ms:.2f})"
                    if ms >= 1.1 else f"Higher projected output ({pts:.1f} pts)"
                )
            else:
                parts.append(
                    f"Tough matchup (score {ms:.2f})"
                    if ms < 0.9 else f"Lower projected output ({pts:.1f} pts)"
                )
            if proj.get('weather_impact'):
                parts.append("adverse weather expected")
            return '. '.join(parts) + '.'

        conf_vals = [start_proj.get('confidence', 'medium'), sit_proj.get('confidence', 'medium')]
        if 'low' in conf_vals:
            overall_conf = 'low'
        elif all(c == 'high' for c in conf_vals):
            overall_conf = 'high'
        else:
            overall_conf = 'medium'

        return {
            'start': {
                'player_id':            start_id,
                'full_name':            start_proj.get('full_name', ''),
                'position':             start_proj.get('position'),
                'team_abbr':            start_proj.get('team_abbr'),
                'headshot_url':         start_proj.get('headshot_url'),
                'projected_points_ppr': start_proj.get('projected_points_ppr', 0.0),
                'matchup_score':        start_proj.get('matchup_score', 1.0),
                'reasoning':            _reasoning(start_proj, True),
            },
            'sit': {
                'player_id':            sit_id,
                'full_name':            sit_proj.get('full_name', ''),
                'position':             sit_proj.get('position'),
                'team_abbr':            sit_proj.get('team_abbr'),
                'headshot_url':         sit_proj.get('headshot_url'),
                'projected_points_ppr': sit_proj.get('projected_points_ppr', 0.0),
                'matchup_score':        sit_proj.get('matchup_score', 1.0),
                'reasoning':            _reasoning(sit_proj, False),
            },
            'confidence': overall_conf,
        }

    # ── Private helpers ──────────────────────────────────────────────────────

    def _get_injury_for_player(self, player_name: str) -> Optional[Any]:
        """Get the most recent injury record matching the player's last name."""
        if not player_name:
            return None
        last = player_name.strip().split()[-1]
        return self.db.fetchone(
            """
            SELECT * FROM injury_reports
            WHERE player_name LIKE ?
            ORDER BY report_date DESC
            LIMIT 1
            """,
            (f'%{last}%',),
        )

    def _get_injury_frequency(self, player_name: str) -> int:
        """Count all injury_reports entries for a player (approximate last-name match)."""
        if not player_name:
            return 0
        last = player_name.strip().split()[-1]
        row = self.db.fetchone(
            "SELECT COUNT(*) AS cnt FROM injury_reports WHERE player_name LIKE ?",
            (f'%{last}%',),
        )
        return int(row['cnt'] or 0) if row else 0

    def _is_starter(self, player_id: int, season: int) -> bool:
        """Return True if the player is marked as a starter in roster_entries."""
        row = self.db.fetchone(
            "SELECT is_starter FROM roster_entries WHERE player_id=? AND season=? LIMIT 1",
            (player_id, season),
        )
        return bool(row and row['is_starter']) if row else False

    def _get_weather_for_matchup(
        self, team_id: int, season: int, week: int
    ) -> Optional[Any]:
        """Fetch game_weather for the team's game in the given week (if any)."""
        game = self.db.fetchone(
            """
            SELECT date, home_team_id FROM games
            WHERE season=?
              AND (CAST(week AS INTEGER)=? OR week=CAST(? AS TEXT))
              AND (home_team_id=? OR away_team_id=?)
            LIMIT 1
            """,
            (season, week, str(week), team_id, team_id),
        )
        if not game:
            return None
        return self.db.fetchone(
            "SELECT * FROM game_weather WHERE home_team_id=? AND game_date=?",
            (game['home_team_id'], str(game['date'])),
        )

    def _get_over_under(
        self, team_id: int, season: int, week: int
    ) -> Optional[float]:
        """Return the over/under from game_odds for the team's game in a given week."""
        game = self.db.fetchone(
            """
            SELECT game_id FROM games
            WHERE season=?
              AND (CAST(week AS INTEGER)=? OR week=CAST(? AS TEXT))
              AND (home_team_id=? OR away_team_id=?)
            LIMIT 1
            """,
            (season, week, str(week), team_id, team_id),
        )
        if not game:
            return None
        odds = self.db.fetchone(
            "SELECT over_under FROM game_odds WHERE game_id=?",
            (game['game_id'],),
        )
        return float(odds['over_under']) if odds and odds['over_under'] else None
