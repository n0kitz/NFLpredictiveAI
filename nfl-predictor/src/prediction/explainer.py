"""SHAP-based feature explanation for ML model predictions."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Feature label mapping ─────────────────────────────────────────────────────

FEATURE_LABELS: Dict[str, str] = {
    "home_win_pct":              "Home Win %",
    "away_win_pct":              "Away Win %",
    "home_weighted_win_pct":     "Home Weighted Win %",
    "away_weighted_win_pct":     "Away Weighted Win %",
    "home_ppg":                  "Home Points/Game",
    "away_ppg":                  "Away Points/Game",
    "home_pag":                  "Home Points Allowed/Game",
    "away_pag":                  "Away Points Allowed/Game",
    "home_point_diff_per_game":  "Home Point Differential",
    "away_point_diff_per_game":  "Away Point Differential",
    "home_sos":                  "Home Strength of Schedule",
    "away_sos":                  "Away Strength of Schedule",
    "home_form_rating":          "Home Recent Form",
    "away_form_rating":          "Away Recent Form",
    "home_strength":             "Home Team Strength",
    "away_strength":             "Away Team Strength",
    "home_home_win_pct":         "Home Win % at Home",
    "away_away_win_pct":         "Away Win % on Road",
    "h2h_home_win_pct":          "Head-to-Head Record",
    "home_rest_days":            "Home Rest Days",
    "away_rest_days":            "Away Rest Days",
    "home_turnover_margin":      "Home Turnover Margin",
    "away_turnover_margin":      "Away Turnover Margin",
    "home_third_down_pct":       "Home 3rd Down Conv %",
    "away_third_down_pct":       "Away 3rd Down Conv %",
    "home_yards_per_play":       "Home Yards/Play",
    "away_yards_per_play":       "Away Yards/Play",
    "home_redzone_efficiency":   "Home Red Zone Efficiency",
    "away_redzone_efficiency":   "Away Red Zone Efficiency",
    "is_playoff":                "Playoff Game",
    "week_of_season":            "Week of Season",
    "home_dynamic_hfa":          "Home Field Advantage",
    "vegas_home_implied_prob":   "Vegas Implied Probability",
    "home_qb_epa_per_play":      "Home QB EPA/Play",
    "away_qb_epa_per_play":      "Away QB EPA/Play",
}

# ── Singleton explainer cache ─────────────────────────────────────────────────

_explainer_cache: Optional[Any] = None
_explainer_model_id: Optional[int] = None


def _unwrap_tree_model(model: Any) -> Any:
    """
    Extract the underlying tree estimator from a CalibratedClassifierCV wrapper.

    shap.TreeExplainer only works on tree models directly, not on sklearn's
    calibration wrapper.  For cv='prefit' there is exactly one inner classifier.
    """
    try:
        from sklearn.calibration import CalibratedClassifierCV
        if isinstance(model, CalibratedClassifierCV):
            return model.calibrated_classifiers_[0].estimator
    except Exception:
        pass
    return model


def get_explainer(model: Optional[Any]) -> Optional[Any]:
    """
    Return a cached shap.TreeExplainer for *model*.

    Creates the explainer on first call; reuses it for subsequent calls
    with the same model object.  Returns None if model is None or shap
    is unavailable.

    If *model* is a CalibratedClassifierCV the inner tree estimator is used
    so that TreeExplainer can still produce SHAP values.
    """
    global _explainer_cache, _explainer_model_id

    if model is None:
        return None

    model_id = id(model)
    if _explainer_cache is not None and _explainer_model_id == model_id:
        return _explainer_cache

    try:
        import shap  # lazy import — shap is optional
        tree_model = _unwrap_tree_model(model)
        _explainer_cache = shap.TreeExplainer(tree_model)
        _explainer_model_id = model_id
        logger.info("SHAP TreeExplainer created for model id=%d", model_id)
        return _explainer_cache
    except Exception as exc:
        logger.warning("Could not create SHAP explainer: %s", exc)
        return None


def generate_shap_explanation(
    home_metrics: Any,
    away_metrics: Any,
    h2h: dict,
    is_playoff: bool,
    week: Any,
    model: Optional[Any],
    feature_names: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """
    Compute SHAP values for a matchup and return the top 8 features.

    Each entry in the returned list is a dict with keys:
        feature        – raw feature name (e.g. "home_turnover_margin")
        label          – human-readable label
        shap_value     – float; positive favours home, negative favours away
        direction      – "home" | "away" | "neutral"
        feature_value  – actual value of the feature for this game

    Returns [] on any error (model absent, shap import fails, etc.).
    """
    if model is None or feature_names is None:
        return []

    try:
        import numpy as np
        from .feature_builder import build_feature_vector, feature_dict_to_array

        explainer = get_explainer(model)
        if explainer is None:
            return []

        feat_dict = build_feature_vector(
            home_metrics, away_metrics, h2h,
            is_playoff=is_playoff, week=week,
        )
        feat_array = feature_dict_to_array(feat_dict)

        # shap_values may be:
        #   list[ndarray]  — sklearn convention; index 1 = class 1 (home win)
        #   ndarray (1, n) — single output
        #   ndarray (2, n, 1) or similar — multi-output
        raw = explainer.shap_values(feat_array.reshape(1, -1))

        if isinstance(raw, list):
            # list of arrays per class
            sv = np.array(raw[1]).flatten()
        else:
            arr = np.array(raw)
            if arr.ndim == 3:
                # (n_classes, n_samples, n_features) or (n_samples, n_features, n_classes)
                sv = arr[1].flatten() if arr.shape[0] == 2 else arr[:, :, 1].flatten()
            else:
                sv = arr.flatten()

        if len(sv) != len(feature_names):
            logger.warning(
                "SHAP values length %d != feature count %d — skipping",
                len(sv), len(feature_names),
            )
            return []

        entries: List[Dict[str, Any]] = []
        for fname, shap_val in zip(feature_names, sv):
            sv_float = float(shap_val)
            if sv_float > 0.005:
                direction = "home"
            elif sv_float < -0.005:
                direction = "away"
            else:
                direction = "neutral"

            entries.append({
                "feature":       fname,
                "label":         FEATURE_LABELS.get(fname, fname),
                "shap_value":    round(sv_float, 6),
                "direction":     direction,
                "feature_value": round(float(feat_dict.get(fname, 0.0)), 4),
            })

        # Top 8 by |shap_value|
        entries.sort(key=lambda e: abs(e["shap_value"]), reverse=True)
        return entries[:8]

    except Exception as exc:
        logger.warning("SHAP explanation failed: %s", exc)
        return []
