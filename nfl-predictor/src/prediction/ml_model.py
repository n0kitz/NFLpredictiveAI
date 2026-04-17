"""
Train and serve an NFL win-probability model using GradientBoostingClassifier.

Training window: seasons 2013-2022 (inclusive).
Test window (OOS): 2023-2024.

Never retrain on startup — training is explicit via CLI or scripts/train_model.py.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from .feature_builder import (
    FEATURE_NAMES,
    build_feature_vector,
    feature_dict_to_array,
    get_rolling_starter_qb_epa,
    _parse_week,
)
from .metrics import calculate_team_metrics

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
MODEL_PATH = _DATA_DIR / "nfl_model.joblib"
FEATURES_PATH = _DATA_DIR / "nfl_model_features.json"
SPREAD_MODEL_PATH = _DATA_DIR / "nfl_spread_model.joblib"

TRAINING_SEASONS = list(range(2013, 2023))   # 2013-2022 inclusive


# ── Dataset builder ──────────────────────────────────────────────────────────

def _h2h_before(db, home_id: int, away_id: int, cutoff_date: str, limit: int = 10) -> dict:
    """Head-to-head record filtered to games strictly before cutoff_date."""
    rows = db.fetchall(
        """
        SELECT winner_id, home_team_id FROM games
        WHERE ((home_team_id = ? AND away_team_id = ?)
            OR (home_team_id = ? AND away_team_id = ?))
          AND home_score IS NOT NULL
          AND date < ?
        ORDER BY date DESC
        LIMIT ?
        """,
        (home_id, away_id, away_id, home_id, cutoff_date, limit),
    )
    team1_wins = sum(1 for r in rows if r["winner_id"] == home_id)
    team2_wins = sum(1 for r in rows if r["winner_id"] == away_id)
    return {
        "team1_wins":   team1_wins,
        "team2_wins":   team2_wins,
        "total_games":  len(rows),
    }



def build_training_dataset(
    db,
    start_season: int = 2013,
    end_season: int = 2022,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build (X, y) for the given season window.

    Each game uses only data available before that game's date (cutoff_date).
    Tied games are excluded (target is binary: 1=home win, 0=away win).

    Returns:
        X: float64 array of shape (n_samples, n_features)
        y: int array of shape (n_samples,)
    """
    games = db.fetchall(
        """
        SELECT g.game_id, g.date, g.season, g.week, g.game_type,
               g.home_team_id, g.away_team_id, g.winner_id
        FROM games g
        WHERE g.season BETWEEN ? AND ?
          AND g.winner_id IS NOT NULL
          AND g.home_score IS NOT NULL
        ORDER BY g.date ASC
        """,
        (start_season, end_season),
    )

    total = len(games)
    print(f"  Building dataset from {total} games ({start_season}-{end_season})…")

    X_rows, y_rows = [], []

    for i, game in enumerate(games):
        game_date  = str(game["date"])[:10]
        season     = game["season"]
        home_id    = game["home_team_id"]
        away_id    = game["away_team_id"]
        winner_id  = game["winner_id"]
        is_playoff = int(game["game_type"] != "regular")
        week       = _parse_week(game["week"])

        try:
            home_m = calculate_team_metrics(
                db, home_id, current_season=season, cutoff_date=game_date
            )
            away_m = calculate_team_metrics(
                db, away_id, current_season=season, cutoff_date=game_date
            )
        except Exception as exc:
            logger.debug("Skipping game %s: %s", game["game_id"], exc)
            continue

        h2h = _h2h_before(db, home_id, away_id, game_date, limit=10)

        week_int = _parse_week(game["week"])
        home_roll_epa = get_rolling_starter_qb_epa(
            db, home_id, before_week=week_int, season=season,
            fallback=home_m.qb_epa_per_play,
        )
        away_roll_epa = get_rolling_starter_qb_epa(
            db, away_id, before_week=week_int, season=season,
            fallback=away_m.qb_epa_per_play,
        )

        feat_dict = build_feature_vector(
            home_m, away_m, h2h, is_playoff, week,
            home_starter_qb_epa=home_roll_epa,
            away_starter_qb_epa=away_roll_epa,
        )
        X_rows.append(feature_dict_to_array(feat_dict))
        y_rows.append(1 if winner_id == home_id else 0)

        if (i + 1) % 100 == 0:
            print(f"    {i + 1}/{total} games…")

    print(f"  Dataset ready: {len(X_rows)} samples, {len(FEATURE_NAMES)} features.")
    return np.array(X_rows, dtype=np.float64), np.array(y_rows, dtype=np.int32)


def build_training_dataset_with_spread(db) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build (X, y_spread) for the spread regression model (home_score - away_score).

    Ties and blowouts (|diff| > 45) are excluded.
    Returns:
        X: float64 array of shape (n_samples, 35)
        y: float array of shape (n_samples,) — home - away point differential
    """
    games = db.fetchall(
        """
        SELECT g.game_id, g.date, g.season, g.week, g.game_type,
               g.home_team_id, g.away_team_id, g.winner_id,
               g.home_score, g.away_score
        FROM games g
        WHERE g.season BETWEEN 2013 AND 2022
          AND g.winner_id IS NOT NULL
          AND g.home_score IS NOT NULL
          AND g.away_score IS NOT NULL
        ORDER BY g.date ASC
        """,
    )

    total = len(games)
    print(f"  Building spread dataset from {total} games (2013-2022)…")

    X_rows, y_rows = [], []

    for i, game in enumerate(games):
        diff = game["home_score"] - game["away_score"]
        # Exclude ties and blowouts > 45 pts
        if diff == 0 or abs(diff) > 45:
            continue

        game_date  = str(game["date"])[:10]
        season     = game["season"]
        home_id    = game["home_team_id"]
        away_id    = game["away_team_id"]
        is_playoff = int(game["game_type"] != "regular")
        week       = _parse_week(game["week"])

        try:
            home_m = calculate_team_metrics(
                db, home_id, current_season=season, cutoff_date=game_date
            )
            away_m = calculate_team_metrics(
                db, away_id, current_season=season, cutoff_date=game_date
            )
        except Exception as exc:
            logger.debug("Skipping game %s: %s", game["game_id"], exc)
            continue

        h2h = _h2h_before(db, home_id, away_id, game_date, limit=10)

        week_int = _parse_week(game["week"])
        home_roll_epa = get_rolling_starter_qb_epa(
            db, home_id, before_week=week_int, season=season,
            fallback=home_m.qb_epa_per_play,
        )
        away_roll_epa = get_rolling_starter_qb_epa(
            db, away_id, before_week=week_int, season=season,
            fallback=away_m.qb_epa_per_play,
        )

        feat_dict = build_feature_vector(
            home_m, away_m, h2h, is_playoff, week,
            home_starter_qb_epa=home_roll_epa,
            away_starter_qb_epa=away_roll_epa,
        )
        X_rows.append(feature_dict_to_array(feat_dict))
        y_rows.append(float(diff))

        if (i + 1) % 100 == 0:
            print(f"    {i + 1}/{total} games…")

    print(f"  Spread dataset ready: {len(X_rows)} samples.")
    return np.array(X_rows, dtype=np.float64), np.array(y_rows, dtype=np.float64)


# ── Training ─────────────────────────────────────────────────────────────────

def train_model(db) -> dict:
    """
    Train a GradientBoostingClassifier on 2013-2022 with internal 5-fold CV
    calibration (CalibratedClassifierCV, method='isotonic', cv=5).

    cv=5 gives isotonic regression ~540 games per calibration fold, avoiding the
    stairstep artefacts produced by cv='prefit' on a single 282-game holdout.
    With cv='prefit' the 55-60% bucket was empty and the 80%+ bucket showed
    -8.8pp under-confidence; internal CV fixes the distribution.

    Returns dict with cv_accuracy, cv_std, fold_accuracies, n_training_samples,
    training_seasons.
    """
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score
    import joblib

    _GBM_PARAMS = dict(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=20,
        random_state=42,
    )

    # ── 1. Build dataset: all 2013-2022 ──────────────────────────────────────
    X_all, y_all = build_training_dataset(db, start_season=2013, end_season=2022)

    print(f"\n  {len(X_all):,} training samples (2013-2022).")

    # ── 2. CV accuracy on 2013-2022 (for reporting — unfitted estimator) ─────
    print("  Computing CV accuracy with TimeSeriesSplit(5)…")
    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = cross_val_score(
        GradientBoostingClassifier(**_GBM_PARAMS),
        X_all, y_all, cv=tscv, scoring="accuracy",
    )
    fold_accs = [round(float(s), 4) for s in cv_scores]
    print(f"  CV fold accuracies: {fold_accs}")
    print(f"  CV mean: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # ── 3. Calibrated model: cv=5 → ~540 games per calibration fold ──────────
    print("  Fitting CalibratedClassifierCV(method='isotonic', cv=5) on 2013-2022…")
    calibrated_model = CalibratedClassifierCV(
        estimator=GradientBoostingClassifier(**_GBM_PARAMS),
        method="isotonic",
        cv=5,
    )
    calibrated_model.fit(X_all, y_all)

    # ── 4. Persist ────────────────────────────────────────────────────────────
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(calibrated_model, MODEL_PATH)
    FEATURES_PATH.write_text(json.dumps(FEATURE_NAMES, indent=2))

    print(f"\n  Calibrated model saved to {MODEL_PATH}")
    print(f"  Feature list saved to {FEATURES_PATH}")

    return {
        "cv_accuracy":        round(float(cv_scores.mean()), 4),
        "cv_std":             round(float(cv_scores.std()), 4),
        "fold_accuracies":    fold_accs,
        "n_training_samples": len(X_all),
        "training_seasons":   "2013-2022 (CalibratedClassifierCV isotonic, cv=5)",
    }


def train_spread_model(db) -> dict:
    """
    Train a GradientBoostingRegressor to predict the home-away point spread.

    Uses TimeSeriesSplit(n_splits=5) for CV. Saves to data/nfl_spread_model.joblib.

    Returns dict with cv_mae, cv_std, fold_maes, n_training_samples.
    """
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score
    import joblib

    X, y = build_training_dataset_with_spread(db)

    print(f"\n  Training GradientBoostingRegressor (spread) on {len(X)} samples…")

    reg = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=20,
        random_state=42,
    )

    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = cross_val_score(reg, X, y, cv=tscv, scoring="neg_mean_absolute_error")
    fold_maes = [round(float(-s), 4) for s in cv_scores]

    print(f"  Spread CV MAE per fold: {fold_maes}")
    print(f"  Spread CV mean MAE: {-cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    print("  Fitting spread model on full training set…")
    reg.fit(X, y)

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(reg, SPREAD_MODEL_PATH)
    print(f"  Spread model saved to {SPREAD_MODEL_PATH}")

    return {
        "cv_mae":             round(float(-cv_scores.mean()), 4),
        "cv_std":             round(float(cv_scores.std()), 4),
        "fold_maes":          fold_maes,
        "n_training_samples": len(X),
    }


# ── Load / predict ───────────────────────────────────────────────────────────

def load_model() -> Tuple[Optional[object], Optional[list]]:
    """
    Load a previously trained model.

    Returns:
        (model, feature_names) if files exist, (None, None) otherwise.
        Never raises.
    """
    try:
        if not MODEL_PATH.exists() or not FEATURES_PATH.exists():
            return None, None
        import joblib
        model = joblib.load(MODEL_PATH)
        feature_names = json.loads(FEATURES_PATH.read_text())
        logger.info("ML model loaded from %s (%d features)", MODEL_PATH, len(feature_names))
        return model, feature_names
    except Exception as exc:
        logger.warning("Could not load ML model: %s — falling back to weighted-sum", exc)
        return None, None


def load_spread_model() -> Optional[object]:
    """Load the spread regression model. Returns None if file does not exist."""
    try:
        if not SPREAD_MODEL_PATH.exists():
            return None
        import joblib
        model = joblib.load(SPREAD_MODEL_PATH)
        logger.info("Spread model loaded from %s", SPREAD_MODEL_PATH)
        return model
    except Exception as exc:
        logger.warning("Could not load spread model: %s", exc)
        return None


def predict_spread(model, feature_array: np.ndarray) -> float:
    """
    Predict the home-away point differential.

    Returns a float clamped to [-28, +28]. Positive = home favoured.
    Returns 0.0 if model is None.
    """
    if model is None:
        return 0.0
    try:
        pred = float(model.predict(feature_array.reshape(1, -1))[0])
        return max(-28.0, min(28.0, pred))
    except Exception as exc:
        logger.warning("predict_spread failed: %s", exc)
        return 0.0


def predict_with_ml(model, feature_array: np.ndarray) -> Tuple[float, float]:
    """
    Run the ML model and return (home_prob, away_prob), both clamped to [0.02, 0.98].

    Args:
        model: Fitted GradientBoostingClassifier (or any sklearn classifier).
        feature_array: 1-D float64 array of shape (34,).

    Returns:
        (home_prob, away_prob)
    """
    proba = model.predict_proba(feature_array.reshape(1, -1))[0]
    # predict_proba returns [P(class=0), P(class=1)] — class 1 = home win
    home_prob = float(proba[1])
    home_prob = max(0.02, min(0.98, home_prob))
    away_prob = 1.0 - home_prob
    return home_prob, away_prob
