"""Survey-weighted evaluation metrics and bootstrap confidence intervals.

All population quantities (prevalence, sensitivity, PPV, share flagged) use the NHANES
MEC exam weights, so they estimate what would happen in the US adult population.
"""
from __future__ import annotations

import warnings

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

EPS = 1e-6


def weighted_quantile(x: np.ndarray, w: np.ndarray, q: float) -> float:
    o = np.argsort(x)
    cw = np.cumsum(w[o]) / w.sum()
    return float(x[o][np.searchsorted(cw, q, side="left").clip(0, len(x) - 1)])


def flag_at_budget(score: np.ndarray, w: np.ndarray, budget: float) -> np.ndarray:
    """Flag the top `budget` share of the (weighted) population by score."""
    thr = weighted_quantile(score, w, 1 - budget)
    return (score >= thr).astype(float) if budget > 0 else np.zeros_like(score)


def operating_point(y: np.ndarray, flag: np.ndarray, w: np.ndarray) -> dict:
    tp = np.sum(w * flag * y)
    pos = np.sum(w * y)
    flagged = np.sum(w * flag)
    ppv = tp / flagged if flagged > 0 else np.nan
    prev = pos / w.sum()
    return {
        "share_flagged": flagged / w.sum(),
        "sensitivity": tp / pos if pos > 0 else np.nan,
        "ppv": ppv,
        "number_needed_to_test": 1 / ppv if ppv and ppv > 0 else np.nan,
        "lift": ppv / prev if prev > 0 else np.nan,
    }


def calibration(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> dict:
    p = np.clip(p, EPS, 1 - EPS)
    logit = np.log(p / (1 - p)).reshape(-1, 1)
    slope = LogisticRegression(C=1e6, max_iter=1000).fit(logit, y, sample_weight=w).coef_[0, 0]
    return {"obs_exp_ratio": float(np.sum(w * y) / np.sum(w * p)), "calibration_slope": float(slope)}


def discrimination(y: np.ndarray, s: np.ndarray, w: np.ndarray) -> dict:
    if len(np.unique(y)) < 2:
        return {"auroc": np.nan, "auprc": np.nan}
    return {"auroc": float(roc_auc_score(y, s, sample_weight=w)),
            "auprc": float(average_precision_score(y, s, sample_weight=w))}


def brier(y, p, w) -> float:
    return float(np.sum(w * (p - y) ** 2) / w.sum())


def bootstrap(fn, n: int, B: int, seed: int) -> tuple[dict, list[dict]]:
    """Run fn(idx) -> dict[str, float] on B resamples; return 2.5/97.5 percentiles."""
    rng = np.random.default_rng(seed)
    draws = [fn(rng.integers(0, n, n)) for _ in range(B)]
    keys = draws[0].keys()
    warnings.filterwarnings("ignore", "All-NaN slice", RuntimeWarning)
    return {k: (float(np.nanpercentile([d[k] for d in draws], 2.5)),
                float(np.nanpercentile([d[k] for d in draws], 97.5))) for k in keys}, draws
