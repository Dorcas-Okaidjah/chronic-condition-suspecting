"""End-to-end pipeline: data -> cohorts -> models -> evaluation -> impact forecast -> report.

    python run_all.py               # real NHANES data (downloads ~30 MB on first run)
    python run_all.py --synthetic   # fake NHANES-shaped data, for testing the code only
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from ccs import config as C  # noqa: E402
from ccs.cohort import TASKS, add_phenotypes, base_eligibility  # noqa: E402
from ccs.data import load_cycle  # noqa: E402
from ccs.evaluate import run_task  # noqa: E402
from ccs.impact import forecast  # noqa: E402
from ccs import report  # noqa: E402

FORECAST_BASELINE = {"diabetes": "ADA risk test (>=5)",  # strongest guideline baseline
                     "ckd": "Guideline risk factor (any of DM/HTN/CVD/age>=60)"}


def data_audit(df: pd.DataFrame) -> pd.DataFrame:
    adults = df[base_eligibility(df)]
    w = adults["weight"]
    rows = []
    for c in adults.columns:
        if c in ("seqn", "cycle", "race"):
            continue
        rows.append({"cycle": df["cycle"].iat[0], "variable": c, "n_adults": len(adults),
                     "pct_missing": float(adults[c].isna().mean())})
    a = adults
    dm_any = ((a["dx_diabetes"] == 1) | (a["lab_diabetes"] == 1))
    checks = {
        "diabetes_total (dx or HbA1c>=6.5)": np.average(dm_any, weights=w),
        "diabetes_undiagnosed_share_of_total": (np.sum(w * ((a["dx_diabetes"] != 1) & (a["lab_diabetes"] == 1)))
                                                / np.sum(w * dm_any)),
        "ckd_lab (eGFR<60 or UACR>=30)": np.average(a["lab_ckd"].fillna(0), weights=w),
        "ckd_unaware_share": (np.sum(w * ((a["lab_ckd"] == 1) & (a["dx_kidney"] != 1)))
                              / np.sum(w * (a["lab_ckd"] == 1))),
    }
    for k, v in checks.items():
        rows.append({"cycle": df["cycle"].iat[0], "variable": f"CHECK {k}", "n_adults": len(a),
                     "pct_missing": np.nan, "weighted_value": float(v)})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true", help="use fake data (tests only)")
    ap.add_argument("--tasks", nargs="*", default=[t.name for t in TASKS])
    ap.add_argument("--n-boot", type=int, default=C.N_BOOTSTRAP)
    ap.add_argument("--n-sims", type=int, default=2000)
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out = Path(args.out)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    train = add_phenotypes(load_cycle(C.TRAIN_CYCLE, synthetic=args.synthetic))
    test = add_phenotypes(load_cycle(C.TEST_CYCLE, synthetic=args.synthetic))
    audit = pd.concat([data_audit(train), data_audit(test)])
    audit.to_csv(out / "data_audit.csv", index=False)
    print("\nData sanity checks (survey-weighted, adults 20+):")
    print(audit[audit.variable.str.startswith("CHECK")][["cycle", "variable", "weighted_value"]]
          .to_string(index=False))

    results, preds, forecasts = [], {}, []
    for task in [t for t in TASKS if t.name in args.tasks]:
        res, p = run_task(task, train, test, n_boot=args.n_boot)
        results.append(res)
        preds[task.name] = p
        p.to_csv(out / f"predictions_{task.name}.csv", index=False)
        for pop in ("all", "65+"):
            forecasts.append(forecast(task, p, FORECAST_BASELINE[task.condition], pop, n_sims=args.n_sims))
        top = p[p.flag_primary == 1].nlargest(10, "p")[["seqn", "age", "female", "p", "y", "reasons"]]
        top.assign(task=task.name).to_csv(out / f"suspect_examples_{task.name}.csv", index=False)

    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    (out / "results.json").write_text(json.dumps({"synthetic": args.synthetic, "results": clean,
                                                  "forecasts": forecasts}, indent=2, default=float))
    report.gain_charts(results, preds, out / "figures" / "gain_charts.png")
    report.calibration_plots(results, preds, out / "figures" / "calibration.png")
    report.subgroup_plot(results, out / "figures" / "subgroups.png")
    report.impact_plot(forecasts, out / "figures" / "impact.png")
    report.write_summary(clean, forecasts, out / "summary.md", synthetic=args.synthetic)

    print(f"\nDone in {time.time() - t0:.0f}s. Headlines:")
    for r in clean:
        b, m = next(iter(r["matched"].items()))
        print(f"  {r['task']:<10} AUROC {r['test'][r['chosen_model']]['auroc']:.3f} | "
              f"same volume as '{b}': cases found {m['baseline']['sensitivity']:.1%} -> "
              f"{m['model']['sensitivity']:.1%}")
    print(f"Full results: {out / 'summary.md'}")


if __name__ == "__main__":
    main()
