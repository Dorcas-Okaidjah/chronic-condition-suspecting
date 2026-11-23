"""Guideline baselines: what a clinic does today without a model.

Each baseline returns (score, flag): a continuous score for ranking metrics and the
binary "screen this patient" decision the guideline actually makes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ada_risk_score(df: pd.DataFrame) -> pd.Series:
    """ADA diabetes risk test, items available in NHANES visit data.

    Omitted: gestational diabetes and physical activity items (2 points max),
    so this version is slightly conservative.  Standard cut-off is >= 5.
    """
    age = df["age"]
    s = np.select([age >= 60, age >= 50, age >= 40], [3, 2, 1], 0).astype(float)
    s += (df["female"] == 0)
    s += (df["fam_dm"] == 1)
    s += ((df["dx_htn"] == 1) | (df["bp_meds"] == 1))
    bmi = df["bmi"]
    s += np.select([bmi >= 40, bmi >= 30, bmi >= 25], [3, 2, 1], 0)
    return pd.Series(s, index=df.index)


def uspstf_flag(df: pd.DataFrame) -> pd.Series:
    """USPSTF 2021: screen adults aged 35-70 with overweight or obesity."""
    return ((df["age"].between(35, 70)) & (df["bmi"] >= 25)).astype(float)


def ckd_risk_count(df: pd.DataFrame) -> pd.Series:
    """Count of guideline CKD-screening risk factors (KDIGO / ADA / NKF style):
    diabetes, hypertension, cardiovascular disease, age >= 60."""
    parts = [
        df["dx_diabetes"] == 1,
        (df["dx_htn"] == 1) | (df["bp_meds"] == 1),
        df["cvd"] == 1,
        df["age"] >= 60,
    ]
    return pd.Series(np.sum(parts, axis=0).astype(float), index=df.index)


def baselines_for(task, df: pd.DataFrame) -> dict[str, tuple[pd.Series, pd.Series]]:
    if task.condition == "diabetes":
        ada = ada_risk_score(df)
        out = {
            "ADA risk test (>=5)": (ada, (ada >= 5).astype(float)),
            "USPSTF age 35-70 & BMI>=25": (uspstf_flag(df) + ada / 100, uspstf_flag(df)),
        }
        if "glucose_serum" in task.features:
            g = df["glucose_serum"]
            out["Random glucose >=140 mg/dL"] = (g, (g >= 140).astype(float))
        return out
    cnt = ckd_risk_count(df)
    return {"Guideline risk factor (any of DM/HTN/CVD/age>=60)": (cnt, (cnt >= 1).astype(float))}
