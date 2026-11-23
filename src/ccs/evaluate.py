"""Train on 2017-2020, evaluate on 2021-2023, compare against guideline baselines."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config as C
from .baselines import baselines_for
from .cohort import Task
from .metrics import (bootstrap, brier, calibration, discrimination, flag_at_budget,
                      operating_point)
from .models import lr_coefficients, reason_codes, select_and_fit

log = logging.getLogger(__name__)
PRIMARY_BUDGET = 0.20
MAX_MISSING = 0.50


def _age_band(a):
    return pd.cut(a, [0, 44, 64, 200], labels=["20-44", "45-64", "65+"]).astype(str)


def run_task(task: Task, train_df: pd.DataFrame, test_df: pd.DataFrame,
             n_boot: int = C.N_BOOTSTRAP) -> tuple[dict, pd.DataFrame]:
    tr, te = task.cohort(train_df), task.cohort(test_df)
    # Schema-drift guard: a question dropped or renamed in one cycle would otherwise show
    # up as "all missing" at test time and silently shift every prediction.
    dropped = [f for f in task.features
               if tr[f].isna().mean() > MAX_MISSING or te[f].isna().mean() > MAX_MISSING]
    if dropped:
        log.warning("[%s] dropping features >%.0f%% missing in a cycle: %s",
                    task.name, 100 * MAX_MISSING, dropped)
    feats = [f for f in task.features if f not in dropped]
    Xtr, ytr, wtr = tr[feats], tr[task.target].to_numpy(), tr["weight"].to_numpy()
    Xte, yte, wte = te[feats], te[task.target].to_numpy(), te["weight"].to_numpy()
    log.info("[%s] train n=%d cases=%d | test n=%d cases=%d", task.name, len(tr), ytr.sum(),
             len(te), yte.sum())

    chosen, fitted, cv = select_and_fit(Xtr, ytr, wtr)
    preds = {name: m.predict_proba(Xte)[:, 1] for name, m in fitted.items()}
    p = preds[chosen]
    base = baselines_for(task, te)

    res: dict = {
        "task": task.name, "title": task.title, "lab": task.lab,
        "n_train": int(len(tr)), "cases_train": int(ytr.sum()),
        "n_test": int(len(te)), "cases_test": int(yte.sum()),
        "prevalence_train_weighted": float(np.average(ytr, weights=wtr)),
        "prevalence_test_weighted": float(np.average(yte, weights=wte)),
        "chosen_model": chosen,
        "features_used": feats,
        "features_dropped": dropped,
        "cv_auroc_train": cv,
        "test": {},
    }
    for name, s in preds.items():
        res["test"][name] = {**discrimination(yte, s, wte), "brier": brier(yte, s, wte),
                             **calibration(yte, s, wte)}
    for bname, (score, _) in base.items():
        res["test"][bname] = discrimination(yte, score.to_numpy(), wte)

    # --- operating points at fixed alert budgets ------------------------------------
    res["budgets"] = {f"{b:.0%}": operating_point(yte, flag_at_budget(p, wte, b), wte)
                      for b in C.ALERT_BUDGETS}

    # --- head-to-head at the SAME testing volume as each guideline ----------------------
    res["matched"] = {}
    for bname, (_, bflag) in base.items():
        bflag = bflag.to_numpy()
        bop = operating_point(yte, bflag, wte)
        mop = operating_point(yte, flag_at_budget(p, wte, bop["share_flagged"]), wte)
        res["matched"][bname] = {"baseline": bop, "model": mop}

    # --- bootstrap CIs ------------------------------------------------------------------
    bflags = {k: v[1].to_numpy() for k, v in base.items()}
    bscores = {k: v[0].to_numpy() for k, v in base.items()}

    def one(idx):
        y, w, s = yte[idx], wte[idx], p[idx]
        out = {"auroc": discrimination(y, s, w)["auroc"]}
        for b in C.ALERT_BUDGETS:
            op = operating_point(y, flag_at_budget(s, w, b), w)
            out[f"sens@{b:.0%}"], out[f"ppv@{b:.0%}"] = op["sensitivity"], op["ppv"]
        for k in base:
            bop = operating_point(y, bflags[k][idx], w)
            mop = operating_point(y, flag_at_budget(s, w, bop["share_flagged"]), w)
            out[f"dsens|{k}"] = mop["sensitivity"] - bop["sensitivity"]
            out[f"dppv|{k}"] = mop["ppv"] - bop["ppv"]
            out[f"dauroc|{k}"] = out["auroc"] - discrimination(y, bscores[k][idx], w)["auroc"]
        return out

    ci, draws = bootstrap(one, len(yte), n_boot, C.RANDOM_STATE)
    res["ci95"] = ci

    # --- subgroup audit at the primary budget -------------------------------------------
    flag = flag_at_budget(p, wte, PRIMARY_BUDGET)
    groups = {
        "sex": np.where(te["female"] == 1, "Female", "Male"),
        "race_ethnicity": te["race"].fillna("Unknown").to_numpy(),
        "age": _age_band(te["age"]).to_numpy(),
        "income": np.where(te["pir"] < 1.3, "PIR<1.3 (low income)",
                           np.where(te["pir"].notna(), "PIR>=1.3", "Unknown")),
    }
    rows = []
    for gname, g in groups.items():
        for level in sorted(set(g)):
            m = g == level
            if m.sum() < 30:
                continue
            op = operating_point(yte[m], flag[m], wte[m])
            rows.append({"group": gname, "level": level, "n": int(m.sum()),
                         "cases": int(yte[m].sum()),
                         "prevalence": float(np.average(yte[m], weights=wte[m])),
                         **op,
                         "obs_exp_ratio": float(np.sum(wte[m] * yte[m]) / np.sum(wte[m] * p[m])),
                         "small_sample": bool(yte[m].sum() < 20)})
    subgroups = pd.DataFrame(rows)
    res["subgroups"] = subgroups.to_dict(orient="records")

    res["coefficients"] = lr_coefficients(fitted["logistic"], feats).to_dict(orient="records")

    out = te[["seqn", "age", "female", "race", "pir", "weight", task.target]].copy()
    out = out.rename(columns={task.target: "y"})
    out["p"] = p
    out["flag_primary"] = flag
    for k, (s, f) in base.items():
        out[f"baseline_flag::{k}"] = f.to_numpy()
    out["reasons"] = reason_codes(fitted["logistic"], Xte)
    if task.condition == "ckd":
        out["ckd_stage3"] = te["lab_ckd_stage3"].to_numpy()
    res["_draws"] = draws
    return res, out
