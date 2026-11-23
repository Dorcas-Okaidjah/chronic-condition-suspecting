"""Figures and the Markdown results summary."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

MODEL_C, BASE_C, MUTED, INK, GRID = "#2a78d6", "#eb6834", "#8a8a85", "#2b2b29", "#e1e0d9"
BASE_MARKERS = ["o", "s", "D"]
plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK, "xtick.color": INK,
    "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "figure.dpi": 150,
})


def _gain_curve(y, p, w):
    o = np.argsort(-p)
    x = np.concatenate([[0], np.cumsum(w[o]) / w.sum()])
    g = np.concatenate([[0], np.cumsum((w * y)[o]) / np.sum(w * y)])
    return x, g


def gain_charts(results, preds, path: Path):
    n = len(results)
    fig, axes = plt.subplots(1 if n <= 2 else 2, 2, figsize=(10, 4.4 if n <= 2 else 8.4))
    for ax, res in zip(np.ravel(axes), results):
        d = preds[res["task"]]
        y, p, w = d["y"].to_numpy(), d["p"].to_numpy(), d["weight"].to_numpy()
        x, g = _gain_curve(y, p, w)
        ax.plot([0, 1], [0, 1], ls="--", lw=1, color=MUTED, label="Random testing")
        ax.plot(x, g, lw=2, color=MODEL_C, label=f"Model ({res['chosen_model']})")
        for (bname, m), mk in zip(res["matched"].items(), BASE_MARKERS):
            b = m["baseline"]
            ax.plot(b["share_flagged"], b["sensitivity"], mk, ms=8, color=BASE_C,
                    mec="white", mew=1.5, label=bname)
        ax.set_title(res["title"], fontsize=10, color=INK, loc="left")
        ax.set_xlabel("Share of eligible adults tested")
        ax.set_ylabel("Share of undiagnosed cases found")
        ax.set_xlim(0, 1), ax.set_ylim(0, 1.02)
        ax.legend(fontsize=7.5, frameon=False, loc="lower right")
    for ax in np.ravel(axes)[n:]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def calibration_plots(results, preds, path: Path, bins: int = 10):
    n = len(results)
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 3.3))
    for ax, res in zip(np.atleast_1d(axes), results):
        d = preds[res["task"]].copy()
        d["bin"] = pd.qcut(d["p"].rank(method="first"), bins, labels=False)
        g = d.groupby("bin").apply(lambda t: pd.Series({
            "pred": np.average(t.p, weights=t.weight), "obs": np.average(t.y, weights=t.weight)}),
            include_groups=False)
        hi = max(g.pred.max(), g.obs.max()) * 1.1
        ax.plot([0, hi], [0, hi], ls="--", lw=1, color=MUTED)
        ax.plot(g.pred, g.obs, "o-", lw=2, ms=6, color=MODEL_C, mec="white", mew=1.2)
        ax.set_title(res["task"], fontsize=10, loc="left")
        ax.set_xlabel("Predicted risk")
        ax.set_ylabel("Observed prevalence")
    fig.suptitle("Calibration on 2021-2023 (deciles of predicted risk)", fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def subgroup_plot(results, path: Path, tasks=("dm_visit", "ckd_visit")):
    sel = [r for r in results if r["task"] in tasks]
    fig, axes = plt.subplots(1, len(sel), figsize=(5.2 * len(sel), 4.6), sharey=True)
    for ax, res in zip(np.atleast_1d(axes), sel):
        s = pd.DataFrame(res["subgroups"])
        s["label"] = s["group"].str.replace("_", "/") + ": " + s["level"]
        s = s.iloc[::-1]
        overall = res["budgets"]["20%"]["sensitivity"]
        ax.axvline(overall, color=MUTED, ls="--", lw=1)
        ax.scatter(s["sensitivity"], s["label"], s=60, color=MODEL_C, edgecolor="white", zorder=3)
        for _, r in s[s.small_sample].iterrows():
            ax.annotate("few cases", (r.sensitivity, r.label), xytext=(6, 0),
                        textcoords="offset points", fontsize=7, color=MUTED, va="center")
        ax.set_xlim(0, 1)
        ax.set_title(f"{res['task']}: sensitivity when flagging top 20%", fontsize=10, loc="left")
        ax.set_xlabel("Share of each group's undiagnosed cases flagged")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def impact_plot(forecasts, path: Path):
    f = [x for x in forecasts if x["population"] == "all"]
    labels = [x["task"] for x in f]
    med = np.array([x["summary"]["incremental_dx"]["p50"] for x in f])
    lo = np.array([x["summary"]["incremental_dx"]["p10"] for x in f])
    hi = np.array([x["summary"]["incremental_dx"]["p90"] for x in f])
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.set_axisbelow(True)
    ax.grid(axis="y", visible=False)
    ax.barh(labels, med, color=MODEL_C, height=0.5)
    ax.errorbar(med, labels, xerr=[med - lo, hi - med], fmt="none", ecolor=INK, capsize=4, lw=1)
    ax.axvline(0, color="#c3c2b7", lw=1)
    for yv, m in enumerate(med):
        ax.text(max(hi[yv], 0) + 0.015 * max(hi.max(), 1), yv, f"{m:.0f}", va="center", fontsize=9, color=INK)
    ax.set_xlabel("Extra confirmed diagnoses per 10,000 adults vs. guideline,\ntesting capacity 20% of panel (median, P10-P90)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------------------
def _pct(x, d=1):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{d}f}%"


def _ci(ci, k, pct=True, d=1):
    lo, hi = ci[k]
    return f"{_pct(lo, d)} to {_pct(hi, d)}" if pct else f"{lo:.3f} to {hi:.3f}"


def write_summary(results, forecasts, path: Path, synthetic: bool):
    L = ["# Results: Undiagnosed Chronic Condition Suspecting", ""]
    if synthetic:
        L += ["> **SYNTHETIC DATA - pipeline test only. These numbers mean nothing.**", ""]
    L += ["Train: NHANES 2017-March 2020. Test: NHANES August 2021-August 2023 (temporal external "
          "validation). All rates are survey-weighted to the US adult population.", ""]

    for r in results:
        if r.get("features_dropped"):
            L.append(f"- {r['task']}: features dropped by the schema-drift guard: {', '.join(r['features_dropped'])}")
    L += ["", "## Discrimination and calibration (test cycle)", "",
          "| Task | n (cases) | Prevalence | Model | AUROC (95% CI) | AUPRC | O/E | Cal. slope | Train CV AUROC |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        t = r["test"][r["chosen_model"]]
        L.append(f"| {r['task']} | {r['n_test']:,} ({r['cases_test']}) | {_pct(r['prevalence_test_weighted'])} "
                 f"| {r['chosen_model']} | {t['auroc']:.3f} ({_ci(r['ci95'], 'auroc', pct=False)}) "
                 f"| {t['auprc']:.3f} | {t['obs_exp_ratio']:.2f} | {t['calibration_slope']:.2f} "
                 f"| {r['cv_auroc_train'][r['chosen_model']]:.3f} |")
    L += ["", "Effect of survey weights on calibration (observed/expected on the test cycle; 1.00 = perfect):", ""]
    for r in results:
        u = r["test"].get("logistic_unweighted (diagnostic)")
        if u:
            L.append(f"- {r['task']}: unweighted training O/E {u['obs_exp_ratio']:.2f} -> "
                     f"survey-weighted O/E {r['test'][r['chosen_model']]['obs_exp_ratio']:.2f}")
    L += ["", "Guideline AUROC on the same test patients:", ""]
    for r in results:
        for b, m in r["matched"].items():
            L.append(f"- {r['task']} / {b}: AUROC {r['test'][b]['auroc']:.3f}; model minus guideline "
                     f"{_ci(r['ci95'], f'dauroc|{b}', pct=False)}")

    L += ["", "## Model vs. guideline at the same testing volume", "",
          "| Task | Guideline | Share tested | Cases found: guideline | Cases found: model | Difference (95% CI) | PPV guideline | PPV model |",
          "|---|---|---|---|---|---|---|---|"]
    for r in results:
        for b, m in r["matched"].items():
            L.append(f"| {r['task']} | {b} | {_pct(m['baseline']['share_flagged'])} "
                     f"| {_pct(m['baseline']['sensitivity'])} | {_pct(m['model']['sensitivity'])} "
                     f"| {_ci(r['ci95'], f'dsens|{b}')} | {_pct(m['baseline']['ppv'])} | {_pct(m['model']['ppv'])} |")

    L += ["", "## Alert-budget operating points (model)", "",
          "| Task | Flag top | Sensitivity (95% CI) | PPV (95% CI) | Tests per case found | Lift |",
          "|---|---|---|---|---|---|"]
    for r in results:
        for b, op in r["budgets"].items():
            L.append(f"| {r['task']} | {b} | {_pct(op['sensitivity'])} ({_ci(r['ci95'], f'sens@{b}')}) "
                     f"| {_pct(op['ppv'])} ({_ci(r['ci95'], f'ppv@{b}')}) "
                     f"| {op['number_needed_to_test']:.1f} | {op['lift']:.1f}x |")

    for r in results:
        if "hybrid_budgets" in r:
            L += ["", f"## {r['task']}: hybrid (lab rule first, then model) vs. model alone", "",
                  "| Flag top | Model sensitivity | Hybrid sensitivity | Hybrid minus model (95% CI) |", "|---|---|---|---|"]
            for b, op in r["hybrid_budgets"].items():
                L.append(f"| {b} | {_pct(r['budgets'][b]['sensitivity'])} | {_pct(op['sensitivity'])} "
                         f"| {_ci(r['ci95'], f'hybrid_minus_model_sens@{b}')} |")

    L += ["", "## Impact forecast per 10,000-adult panel (median [P10, P90])", "",
          f"Capacity: outreach testing for {forecasts[0]['capacity']:.0%} of the panel. Guideline = test "
          "guideline-eligible patients (random draw if more are eligible than capacity); model = test top-ranked. "
          "Assumptions and ranges are in `src/ccs/config.py`.", "",
          "| Task | Population | vs. guideline | Tests (model) | Extra confirmed dx | P(extra > 0) | Lab $ per dx: model / guideline | Annual RAF value of extra dx |",
          "|---|---|---|---|---|---|---|---|"]
    for f in forecasts:
        s = f["summary"]
        fmt = lambda k, d=0, pre="": f"{pre}{s[k]['p50']:,.{d}f} [{pre}{s[k]['p10']:,.{d}f}, {pre}{s[k]['p90']:,.{d}f}]"  # noqa: E731
        raf = fmt("incremental_raf_value_usd", pre="$") if f["population"] == "65+" else "-"
        L.append(f"| {f['task']} | {f['population']} | {f['baseline']} | {fmt('tests_ordered')} "
                 f"| {fmt('incremental_dx', 1)} | {_pct(s['prob_incremental_dx_positive'], 0)} "
                 f"| ${s['lab_cost_per_dx_model']['p50']:,.0f} / ${s['lab_cost_per_dx_guideline']['p50']:,.0f} | {raf} |")

    L += ["", "## Subgroup audit (flag top 20%)", "",
          "| Task | Group | n (cases) | Prevalence | Sensitivity | PPV | O/E |", "|---|---|---|---|---|---|---|"]
    for r in results:
        for g in r["subgroups"]:
            flag = " *" if g["small_sample"] else ""
            L.append(f"| {r['task']} | {g['group']}: {g['level']}{flag} | {g['n']:,} ({g['cases']}) "
                     f"| {_pct(g['prevalence'])} | {_pct(g['sensitivity'])} | {_pct(g['ppv'])} | {g['obs_exp_ratio']:.2f} |")
    L += ["", "\\* fewer than 20 cases: treat as directional only.", ""]
    path.write_text("\n".join(L))
