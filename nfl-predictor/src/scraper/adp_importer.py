"""
Real ADP (average draft position) ingestion.

Draft rankings synthesize ADP as the overall rank, which makes "value vs
market" analysis impossible. Two ingestion paths fill the ``player_adp``
table, which ``generate_draft_rankings`` merges in preference to the
synthetic rank:

1. **Live fetch** (``fetch_ffc_adp``) — consensus ADP from Fantasy Football
   Calculator's public JSON API. No download and no account, so this is the
   default path and can be re-run whenever the market moves.
2. **CSV import** (``parse_adp_csv``) — a FantasyPros cheat-sheet export or a
   simple ``name,adp`` file, for when you want one specific source.

Both funnel into ``import_adp_entries`` for matching and upserting.
"""

import csv
import io
import logging
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from .http import get_with_retry
from .player_weekly_importer import _match_player_id

logger = logging.getLogger(__name__)

FFC_ADP_URL = "https://fantasyfootballcalculator.com/api/v1/adp/{fmt}"

# Our scoring keys -> the format segment FFC expects.
FFC_SCORING: Dict[str, str] = {
    "standard": "standard",
    "half_ppr": "half-ppr",
    "ppr": "ppr",
}

# FFC's position labels differ from ours in two places.
_POSITION_ALIASES = {"PK": "K", "DEF": "DST"}


class AdpEntry(NamedTuple):
    """One market ADP observation, normalized to our position vocabulary."""

    name: str
    position: str
    team: str
    adp: float


def ffc_url(season: int, scoring: str = "standard", teams: int = 10) -> str:
    """Build the FFC ADP endpoint for a scoring format and league size.

    Note: FFC accepts and echoes ``teams``, but as of 2026-08-21 it returns
    the same pooled ADP for every league size (identical values and
    ``total_drafts`` for teams=8 and teams=14). We still send it — it is the
    documented parameter and may start segmenting — but the result must not
    be presented as tuned to league size.
    """
    fmt = FFC_SCORING.get(scoring)
    if fmt is None:
        raise ValueError(
            f"Unsupported scoring {scoring!r}; expected one of {sorted(FFC_SCORING)}"
        )
    return f"{FFC_ADP_URL.format(fmt=fmt)}?teams={teams}&year={season}&position=all"


def parse_ffc_adp(payload: Dict[str, Any]) -> List[AdpEntry]:
    """Normalize an FFC API payload into AdpEntry rows.

    Rows without a usable name or a numeric ADP are skipped rather than
    guessed at.
    """
    entries: List[AdpEntry] = []
    for row in payload.get("players") or []:
        name = (row.get("name") or "").strip()
        raw_adp = row.get("adp")
        if not name or raw_adp is None:
            continue
        try:
            adp = float(raw_adp)
        except (TypeError, ValueError):
            continue
        position = (row.get("position") or "").strip().upper()
        entries.append(
            AdpEntry(
                name=name,
                position=_POSITION_ALIASES.get(position, position),
                team=(row.get("team") or "").strip().upper(),
                adp=adp,
            )
        )
    return entries


def fetch_ffc_adp(
    season: int,
    scoring: str = "standard",
    teams: int = 10,
    session: Optional[Any] = None,
    timeout: float = 20.0,
) -> List[AdpEntry]:
    """Fetch current consensus ADP from Fantasy Football Calculator."""
    url = ffc_url(season=season, scoring=scoring, teams=teams)
    logger.info("Fetching ADP: %s", url)
    resp = get_with_retry(url, session=session, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"ADP fetch failed: HTTP {resp.status_code} for {url}")
    entries = parse_ffc_adp(resp.json())
    logger.info("ADP fetch: %d players returned", len(entries))
    return entries


def _resolve_player_id(db, entry: AdpEntry) -> Optional[int]:
    """Map an ADP row to our player_id.

    Team defenses have no real player behind them — FFC calls them
    "Seattle Defense" while we store synthetic ``DST-{abbr}`` players — so
    they resolve by team abbreviation instead of by name.
    """
    if entry.position == "DST":
        if not entry.team:
            return None
        row = db.fetchone(
            "SELECT player_id FROM players WHERE espn_id = ? LIMIT 1",
            (f"DST-{entry.team}",),
        )
        return int(row["player_id"]) if row else None
    return _match_player_id(db, entry.name, entry.position)


def import_adp_entries(
    db, entries: List[AdpEntry], season: int, source: str = "ffc"
) -> Tuple[int, List[str]]:
    """Match ADP entries to players and upsert into player_adp.

    Returns (matched_count, unmatched_names).
    """
    matched = 0
    unmatched: List[str] = []
    for entry in entries:
        player_id = _resolve_player_id(db, entry)
        if player_id is None:
            unmatched.append(entry.name)
            continue
        db.execute(
            "INSERT OR REPLACE INTO player_adp (season, player_id, adp, source) "
            "VALUES (?, ?, ?, ?)",
            (season, player_id, entry.adp, source),
        )
        matched += 1
    db.commit()
    logger.info("ADP import: %d matched, %d unmatched", matched, len(unmatched))
    return matched, unmatched


def evaluate_adp_import(matched: int, total: int) -> Tuple[bool, str]:
    """Classify an ADP import so a silent no-op cannot pass for success.

    An import that matched nothing is a failure even without an exception:
    the draft board would quietly fall back to synthetic rank ADP and every
    value-vs-market number would be meaningless.
    """
    coverage = f"{matched}/{total}"
    if matched == 0:
        return False, (
            f"FAILED: no ADP rows matched ({coverage}). The draft board would "
            "fall back to synthetic rank ADP — check that this season's "
            "rosters are imported before trusting value-vs-market."
        )
    if total and matched / total < 0.8:
        return True, (
            f"PARTIAL: only {coverage} ADP rows matched a known player. "
            "Unmatched names are usually rookies or players not yet on a "
            "roster — re-run after the next roster refresh."
        )
    return True, f"OK: {coverage} ADP rows matched."


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
        (fields[k] for k in ("player name", "player", "name") if k in fields), None
    )
    adp_field = next(
        (fields[k] for k in ("adp", "avg", "avg.", "rk", "rank") if k in fields), None
    )
    if not name_field or not adp_field:
        return []

    rows: List[Tuple[str, float]] = []
    for r in reader:
        name = (r.get(name_field) or "").strip()
        raw = (r.get(adp_field) or "").strip().replace(",", "")
        if not name or not raw:
            continue
        try:
            rows.append((name, float(raw)))
        except ValueError:
            continue
    return rows


def import_adp(
    db, csv_text: str, season: int, source: str = "csv"
) -> Tuple[int, List[str]]:
    """Match CSV ADP rows to players and upsert into player_adp.

    A CSV carries no position or team column, so entries go in with those
    fields blank and match by name alone.

    Returns (matched_count, unmatched_names).
    """
    entries = [
        AdpEntry(name=name, position="", team="", adp=adp)
        for name, adp in parse_adp_csv(csv_text)
    ]
    return import_adp_entries(db, entries, season, source)
