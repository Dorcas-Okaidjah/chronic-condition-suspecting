"""Phenotypes and prediction tasks.

Each Task answers one product question a PCP-facing assistant would ask:

  dm_visit  Who, among adults with no diabetes diagnosis, should get an HbA1c?
            (uses only what is known at a routine visit -- no glucose labs)
  dm_bmp    Same question when a basic metabolic panel (random serum glucose,
            creatinine) is already on file.
  ckd_visit Who, among adults with no kidney-disease diagnosis, has undiagnosed CKD?
  alb_bmp   Among those whose eGFR on file is normal (>=60), who should get a
            urine albumin-creatinine ratio?  This is the "missing UACR" gap:
            low eGFR is easy to catch from labs; albuminuria is not, because
            UACR is rarely ordered.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from . import config as C


def base_eligibility(df: pd.DataFrame) -> pd.Series:
    return (df["age"] >= C.MIN_AGE) & (df["pregnant"] != 1) & (df["weight"] > 0)


def add_phenotypes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lab_diabetes"] = (df["hba1c"] >= C.HBA1C_DIABETES).astype(float).where(df["hba1c"].notna())
    low_egfr = df["egfr"] < C.EGFR_CKD
    high_uacr = df["uacr"] >= C.UACR_CKD
    df["lab_ckd"] = (low_egfr | high_uacr).astype(float).where(df["egfr"].notna() & df["uacr"].notna())
    df["lab_ckd_stage3"] = (low_egfr & (df["egfr"] >= C.EGFR_STAGE3_LOW)).astype(float)
    df["albuminuria"] = high_uacr.astype(float).where(df["uacr"].notna())
    return df


@dataclass
class Task:
    name: str
    title: str
    condition: str            # 'diabetes' or 'ckd' (drives baselines & impact)
    lab: str                  # confirmatory test the flag triggers
    features: list[str]
    eligible: Callable[[pd.DataFrame], pd.Series]
    target: str
    notes: str = ""
    hybrid_rule: Callable[[pd.DataFrame], pd.Series] | None = None
    extra: dict = field(default_factory=dict)

    def cohort(self, df: pd.DataFrame) -> pd.DataFrame:
        m = base_eligibility(df) & self.eligible(df) & df[self.target].notna()
        return df.loc[m].reset_index(drop=True)


def _no_dm_dx(df):
    return df["dx_diabetes"] != 1


def _no_ckd_dx(df):
    return df["dx_kidney"] != 1


TASKS = [
    Task("dm_visit", "Undiagnosed diabetes - visit data only", "diabetes", "hba1c",
         C.VISIT_FEATURES + ["dx_prediabetes", "dx_borderline"], _no_dm_dx, "lab_diabetes"),
    Task("dm_bmp", "Undiagnosed diabetes - visit + BMP on file", "diabetes", "hba1c",
         C.VISIT_FEATURES + ["dx_prediabetes", "dx_borderline", "glucose_serum"],
         lambda d: _no_dm_dx(d) & d["glucose_serum"].notna(), "lab_diabetes",
         hybrid_rule=lambda d: d["glucose_serum"] >= 140),
    Task("ckd_visit", "Undiagnosed CKD - visit data only", "ckd", "uacr",
         C.VISIT_FEATURES + ["dx_diabetes", "dx_prediabetes", "dx_borderline"], _no_ckd_dx, "lab_ckd"),
    Task("alb_bmp", "Albuminuria with normal eGFR - who needs a UACR", "ckd", "uacr",
         C.VISIT_FEATURES + ["dx_diabetes", "dx_prediabetes", "dx_borderline"] + C.BMP_FEATURES,
         lambda d: _no_ckd_dx(d) & (d["egfr"] >= C.EGFR_CKD), "albuminuria"),
]
TASKS_BY_NAME = {t.name: t for t in TASKS}
