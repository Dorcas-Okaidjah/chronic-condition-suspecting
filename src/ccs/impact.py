"""Forecast the impact of deploying a suspecting model in a primary-care panel.

Question answered: a care team has capacity to send outreach testing to a fixed share
of its panel this year (default 20%).  Guideline strategy: test patients who meet the
guideline, chosen at random if more are eligible than capacity allows.  Model
strategy: test the top-ranked patients.  How many additional confirmed diagnoses per
10,000 adults does the model strategy get, what does the extra testing cost, and -- for a Medicare
Advantage-like (65+) panel -- what is the risk-adjustment value of documenting those
real, confirmed conditions?

Uncertainty combines (a) sampling uncertainty in model performance, via bootstrap
resampling of the 2021-2023 test participants, and (b) operational uncertainty in
the assumptions in config.IMPACT, via triangular distributions.  Revenue is reported
only for conditions that are lab-confirmed and documented; the clinical outcome
(people diagnosed and treated earlier) is the primary metric.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .metrics import flag_at_budget


def _tri(rng, lo_mode_hi):
    lo, mode, hi = lo_mode_hi
    return rng.triangular(lo, mode, hi)


def _payable(task, df: pd.DataFrame) -> np.ndarray:
    """Cases that map to a CMS-HCC V28 payment category."""
    if task.condition == "diabetes":
        return df["y"].to_numpy()
    if "ckd_stage3" in df:
        return (df["y"].to_numpy() * df["ckd_stage3"].to_numpy())
    return np.zeros(len(df))


def _rates_for(task, df, baseline, capacity, idx=None):
    d = df if idx is None else df.iloc[idx]
    y, w = d["y"].to_numpy(), d["weight"].to_numpy()
    pay = _payable(task, d)
    W = w.sum()
    bflag = d[f"baseline_flag::{baseline}"].to_numpy()
    eligible = np.sum(w * bflag) / W
    # guideline: random draw among eligible patients, up to capacity
    frac = min(1.0, capacity / eligible) if eligible > 0 else 0.0
    mflag = flag_at_budget(d["p"].to_numpy(), w, capacity)
    return {
        "share_model": capacity,
        "share_base": eligible * frac,
        "tp_model": np.sum(w * mflag * y) / W,
        "tp_base": frac * np.sum(w * bflag * y) / W,
        "pay_model": np.sum(w * mflag * pay) / W,
        "pay_base": frac * np.sum(w * bflag * pay) / W,
    }


def _panel(r, a, task, N):
    tests = N * r["share_model"] * a["complete"]
    tests_base = N * r["share_base"] * a["complete"]
    new_dx_model = N * r["tp_model"] * a["complete"] * a["confirm"]
    new_dx_base = N * r["tp_base"] * a["complete"] * a["confirm"]
    incr = new_dx_model - new_dx_base
    raf_key = "diabetes" if task.condition == "diabetes" else "ckd_stage3"
    incr_pay = N * (r["pay_model"] - r["pay_base"]) * a["complete"] * a["confirm"]
    return {
        "tests_ordered": tests,
        "new_dx_guideline": new_dx_base,
        "new_dx_model": new_dx_model,
        "incremental_dx": incr,
        "lab_cost_usd": tests * a["cost"],
        "lab_cost_per_dx_model": tests * a["cost"] / new_dx_model if new_dx_model > 0 else np.nan,
        "lab_cost_per_dx_guideline": tests_base * a["cost"] / new_dx_base if new_dx_base > 0 else np.nan,
        "incremental_raf_value_usd": incr_pay * C.IMPACT["raf"][raf_key] * a["usd_raf"],
    }


def forecast(task, preds: pd.DataFrame, baseline: str, population: str = "all",
             capacity: float = 0.20, n_sims: int = 2000, seed: int = C.RANDOM_STATE) -> dict:
    df = preds if population == "all" else preds[preds["age"] >= 65].reset_index(drop=True)
    N = C.IMPACT["panel_size"]
    rng = np.random.default_rng(seed)
    sims = []
    for _ in range(n_sims):
        idx = rng.integers(0, len(df), len(df))
        a = {"complete": _tri(rng, C.IMPACT["test_completion"]),
             "confirm": _tri(rng, C.IMPACT["confirm_and_document"]),
             "cost": _tri(rng, C.IMPACT["lab_cost_usd"][task.lab]),
             "usd_raf": _tri(rng, C.IMPACT["usd_per_raf_year"])}
        sims.append(_panel(_rates_for(task, df, baseline, capacity, idx), a, task, N))
    sims = pd.DataFrame(sims)
    summary = {k: {"p10": float(sims[k].quantile(.1)), "p50": float(sims[k].quantile(.5)),
                   "p90": float(sims[k].quantile(.9))} for k in sims.columns}
    summary["prob_incremental_dx_positive"] = float((sims["incremental_dx"] > 0).mean())
    return {"task": task.name, "baseline": baseline, "population": population,
            "panel_size": N, "capacity": capacity, "n_test_rows": int(len(df)), "summary": summary,
            "tornado": tornado(task, df, baseline, capacity)}


def tornado(task, df, baseline, capacity) -> list[dict]:
    """One-at-a-time sensitivity of incremental diagnoses and RAF value."""
    r = _rates_for(task, df, baseline, capacity)
    mode = {"complete": C.IMPACT["test_completion"][1], "confirm": C.IMPACT["confirm_and_document"][1],
            "cost": C.IMPACT["lab_cost_usd"][task.lab][1], "usd_raf": C.IMPACT["usd_per_raf_year"][1]}
    ranges = {"complete": C.IMPACT["test_completion"], "confirm": C.IMPACT["confirm_and_document"],
              "usd_raf": C.IMPACT["usd_per_raf_year"]}
    N = C.IMPACT["panel_size"]
    rows = []
    for k, (lo, _, hi) in ranges.items():
        low = _panel(r, {**mode, k: lo}, task, N)
        high = _panel(r, {**mode, k: hi}, task, N)
        rows.append({"assumption": k, "low": lo, "high": hi,
                     "incremental_dx_low": low["incremental_dx"], "incremental_dx_high": high["incremental_dx"],
                     "raf_value_low": low["incremental_raf_value_usd"],
                     "raf_value_high": high["incremental_raf_value_usd"]})
    return rows
