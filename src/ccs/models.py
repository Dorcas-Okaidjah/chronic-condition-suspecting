"""Candidate models, model selection on the training cycle only, and reason codes."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C

PARSIMONY_MARGIN = 0.01  # prefer the explainable model unless GBM wins by > 0.01 AUROC


def make_models() -> dict[str, Pipeline | HistGradientBoostingClassifier]:
    return {
        "logistic": Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("lr", LogisticRegression(C=1.0, max_iter=2000)),
        ]),
        "gbm": HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0,
            min_samples_leaf=40, random_state=C.RANDOM_STATE),
    }


def cross_val_auc(model_name: str, X: pd.DataFrame, y: np.ndarray, w: np.ndarray, k: int = 5) -> float:
    """Survey-weighted out-of-fold AUROC within the training cycle."""
    oof = np.zeros(len(y))
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=C.RANDOM_STATE)
    for tr, va in skf.split(X, y):
        m = make_models()[model_name]
        m.fit(X.iloc[tr], y[tr])
        oof[va] = m.predict_proba(X.iloc[va])[:, 1]
    return float(roc_auc_score(y, oof, sample_weight=w))


def select_and_fit(X: pd.DataFrame, y: np.ndarray, w: np.ndarray):
    """Pick a model by training-cycle CV only (the test cycle is never peeked at)."""
    cv = {name: cross_val_auc(name, X, y, w) for name in make_models()}
    chosen = "gbm" if cv["gbm"] > cv["logistic"] + PARSIMONY_MARGIN else "logistic"
    fitted = {}
    for name, m in make_models().items():
        m.fit(X, y)
        fitted[name] = m
    return chosen, fitted, cv


def _feature_names(imp: SimpleImputer, columns: list[str]) -> list[str]:
    names = list(columns)
    if imp.indicator_ is not None:
        names += [f"missing_{columns[i]}" for i in imp.indicator_.features_]
    return names


def reason_codes(lr_pipe: Pipeline, X: pd.DataFrame, top: int = 3) -> list[str]:
    """Top positive contributors (coef x standardized value) for each row.

    This is the 'why was this patient flagged' line a physician would see.
    """
    imp, sc, lr = (lr_pipe.named_steps[k] for k in ("impute", "scale", "lr"))
    names = _feature_names(imp, list(X.columns))
    contrib = sc.transform(imp.transform(X)) * lr.coef_[0]
    binary = {c for c in X.columns if set(X[c].dropna().unique()) <= {0.0, 1.0}}
    out = []
    for r, row in enumerate(contrib):
        parts = []
        for i in np.argsort(row)[::-1][:top]:
            if row[i] <= 0:
                continue
            n = names[i]
            if n in X.columns and n not in binary and pd.notna(X.iloc[r][n]):
                parts.append(f"{n}={X.iloc[r][n]:.0f}")
            else:
                parts.append(n)
        out.append("; ".join(parts))
    return out


def lr_coefficients(lr_pipe: Pipeline, columns: list[str]) -> pd.DataFrame:
    imp, lr = lr_pipe.named_steps["impute"], lr_pipe.named_steps["lr"]
    names = _feature_names(imp, list(columns))
    return (pd.DataFrame({"feature": names, "coef_per_sd": lr.coef_[0]})
            .assign(odds_ratio_per_sd=lambda d: np.exp(d.coef_per_sd))
            .sort_values("coef_per_sd", ascending=False))
