"""
Real ADP (average draft position) ingestion.

Draft rankings synthesize ADP as the overall rank, which makes "value vs
market" analysis impossible. This module ingests an ADP CSV export — a
FantasyPros cheat-sheet download or a simple ``name,adp`` file — into the
``player_adp`` table, which ``generate_draft_rankings`` merges in preference
to the synthetic rank.
"""

import csv
import io
import logging
from typing import List, Tuple

from .player_weekly_importer import _match_player_id

logger = logging.getLogger(__name__)


def parse_adp_csv(text: str) -> List[Tuple[str, float]]:
    """Parse an ADP CSV into (player_name, adp) tuples.

    Supports two shapes:
    - FantasyPros export: has a "PLAYER NAME" column; the "RK" rank column is
      used as ADP (their cheat sheets carry rank, ECR and stars, not raw ADP).
    - Simple: `name,adp` (or `player,adp`) header.
    """
    if not text.strip():
        return []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    fields = {f.strip().lower(): f for f in reader.fieldnames}

    name_field = next(
        (fields[k] for k in ('player name', 'player', 'name') if k in fields), None)
    adp_field = next(
        (fields[k] for k in ('adp', 'avg', 'avg.', 'rk', 'rank') if k in fields), None)
    if not name_field or not adp_field:
        return []

    rows: List[Tuple[str, float]] = []
    for r in reader:
        name = (r.get(name_field) or '').strip()
        raw = (r.get(adp_field) or '').strip().replace(',', '')
        if not name or not raw:
            continue
        try:
            rows.append((name, float(raw)))
        except ValueError:
            continue
    return rows


def import_adp(db, csv_text: str, season: int,
               source: str = 'csv') -> Tuple[int, List[str]]:
    """Match ADP rows to players and upsert into player_adp.

    Returns (matched_count, unmatched_names).
    """
    matched = 0
    unmatched: List[str] = []
    for name, adp in parse_adp_csv(csv_text):
        player_id = _match_player_id(db, name, '')
        if player_id is None:
            unmatched.append(name)
            continue
        db.execute(
            "INSERT OR REPLACE INTO player_adp (season, player_id, adp, source) "
            "VALUES (?, ?, ?, ?)",
            (season, player_id, adp, source),
        )
        matched += 1
    db.commit()
    logger.info("ADP import: %d matched, %d unmatched", matched, len(unmatched))
    return matched, unmatched
