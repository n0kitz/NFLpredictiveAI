"""
Per-position ML fantasy projection model (GradientBoostingRegressor + SHAP).

One model per position (QB, RB, WR, TE). Each predicts PPR fantasy points for
a single player-week from the 13-feature vector defined in player_features.
SHAP TreeExplainer gives per-prediction feature contributions.

Model files live in data/player_models/<pos>_model.joblib. Loading is lazy
and silent — if a model is absent, inference returns None and the caller
falls back to the heuristic path in FantasyScorer.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .player_features import FEATURE_LABELS, FEATURE_NAMES

logger = logging.getLogger(__name__)

MODEL_VERSION = "ml-v2"  # Phase 2: 16-feature vector (added opp_pace, opp_proe, opp_pos_dvp_6wk)

_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "player_models"


def model_path(position: str) -> Path:
    return _DATA_DIR / f"{position.upper()}_model.joblib"


def meta_path(position: str) -> Path:
    return _DATA_DIR / f"{position.upper()}_meta.json"


# ── Training ─────────────────────────────────────────────────────────────────

def train_position_model(
    X: np.ndarray, y: np.ndarray, position: str,
) -> Dict[str, Any]:
    """Train a GradientBoostingRegressor for one position and persist it.

    Returns a dict with cv_mae, n_training_samples, and the path written.
    Raises if X is empty.
    """
    if X.size == 0 or y.size == 0:
        raise ValueError(f"No training samples for position {position}")

    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import KFold, cross_val_score
    import joblib

    reg = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=20,
        random_state=42,
    )

    # KFold CV for MAE reporting
    n_splits = min(5, max(2, X.shape[0] // 50))
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    cv_scores = cross_val_score(reg, X, y, cv=kf, scoring='neg_mean_absolute_error')
    mae = float(-cv_scores.mean())
    std = float(cv_scores.std())

    reg.fit(X, y)

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    mpath = model_path(position)
    joblib.dump(reg, mpath)
    metapath = meta_path(position)
    metapath.write_text(json.dumps({
        'version':            MODEL_VERSION,
        'position':           position,
        'features':           FEATURE_NAMES,
        'cv_mae':             round(mae, 4),
        'cv_std':             round(std, 4),
        'n_training_samples': int(X.shape[0]),
    }, indent=2))
    logger.info(
        "Trained %s model: %d samples, CV MAE %.2f ± %.2f → %s",
        position, X.shape[0], mae, std, mpath,
    )
    return {
        'position': position,
        'cv_mae': round(mae, 4),
        'cv_std': round(std, 4),
        'n_training_samples': int(X.shape[0]),
        'model_path': str(mpath),
    }


# ── Loading / inference ──────────────────────────────────────────────────────

class PlayerModelCache:
    """Lazy loader for per-position models + SHAP explainers."""

    def __init__(self) -> None:
        self._models: Dict[str, Any] = {}
        self._explainers: Dict[str, Any] = {}
        self._attempted: set = set()

    def get_model(self, position: str) -> Optional[Any]:
        pos = position.upper()
        if pos in self._models:
            return self._models[pos]
        if pos in self._attempted:
            return None
        self._attempted.add(pos)
        mpath = model_path(pos)
        if not mpath.exists():
            return None
        try:
            import joblib
            model = joblib.load(mpath)
            self._models[pos] = model
            logger.info("Loaded player model for %s from %s", pos, mpath)
            return model
        except Exception as exc:
            logger.warning("Could not load player model for %s: %s", pos, exc)
            return None

    def get_explainer(self, position: str) -> Optional[Any]:
        pos = position.upper()
        if pos in self._explainers:
            return self._explainers[pos]
        model = self.get_model(pos)
        if model is None:
            return None
        try:
            import shap
            exp = shap.TreeExplainer(model)
            self._explainers[pos] = exp
            return exp
        except Exception as exc:
            logger.warning("Could not build SHAP explainer for %s: %s", pos, exc)
            return None


_cache = PlayerModelCache()


def get_cache() -> PlayerModelCache:
    return _cache


def predict_player_points(
    feature_array: np.ndarray, position: str,
) -> Optional[float]:
    """Predict PPR fantasy points. Returns None if no model is loaded."""
    model = _cache.get_model(position)
    if model is None:
        return None
    try:
        pred = float(model.predict(feature_array.reshape(1, -1))[0])
        return max(0.0, pred)
    except Exception as exc:
        logger.warning("predict_player_points(%s) failed: %s", position, exc)
        return None


def explain_player_prediction(
    feature_array: np.ndarray, feature_dict: Dict[str, float], position: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Return the top-k SHAP contributions for a player-week prediction.

    Each entry has feature, label, shap_value, direction ('up'|'down'|'neutral'),
    and feature_value. Returns [] if SHAP or the model is unavailable.
    """
    explainer = _cache.get_explainer(position)
    if explainer is None:
        return []
    try:
        raw = explainer.shap_values(feature_array.reshape(1, -1))
        arr = np.array(raw).flatten()
        if arr.size != len(FEATURE_NAMES):
            return []
        entries: List[Dict[str, Any]] = []
        for fname, sv in zip(FEATURE_NAMES, arr):
            svf = float(sv)
            if svf > 0.05:
                direction = 'up'
            elif svf < -0.05:
                direction = 'down'
            else:
                direction = 'neutral'
            entries.append({
                'feature':       fname,
                'label':         FEATURE_LABELS.get(fname, fname),
                'shap_value':    round(svf, 4),
                'direction':     direction,
                'feature_value': round(float(feature_dict.get(fname, 0.0)), 3),
            })
        entries.sort(key=lambda e: abs(e['shap_value']), reverse=True)
        return entries[:top_k]
    except Exception as exc:
        logger.warning("SHAP explanation failed for %s: %s", position, exc)
        return []


def model_info() -> Dict[str, Any]:
    """Return a summary of which models are available on disk (for diagnostics)."""
    out: Dict[str, Any] = {'version': MODEL_VERSION, 'positions': {}}
    for pos in ('QB', 'RB', 'WR', 'TE'):
        mpath = model_path(pos)
        mp = meta_path(pos)
        exists = mpath.exists()
        meta = None
        if mp.exists():
            try:
                meta = json.loads(mp.read_text())
            except Exception:
                meta = None
        out['positions'][pos] = {
            'loaded': exists,
            'path': str(mpath) if exists else None,
            'meta': meta,
        }
    return out
