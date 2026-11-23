"""Fast checks that run without network access (synthetic NHANES-shaped data)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ccs import config as C  # noqa: E402
from ccs.baselines import ada_risk_score  # noqa: E402
from ccs.cohort import TASKS, add_phenotypes  # noqa: E402
from ccs.data import ckd_epi_2021, load_cycle  # noqa: E402
from ccs.evaluate import run_task  # noqa: E402
from ccs.impact import forecast  # noqa: E402
from ccs.metrics import flag_at_budget, operating_point  # noqa: E402


def test_ckd_epi_2021_reference_values():
    # Matches the NKF CKD-EPI 2021 calculator (50M Scr 1.0 -> 92; 50F Scr 0.7 -> 105)
    egfr = ckd_epi_2021(pd.Series([1.0, 0.7, 2.0]), pd.Series([50, 50, 70]), pd.Series([0, 1, 0]))
    assert egfr.round(0).tolist() == [92.0, 105.0, 35.0]


def test_ada_score_bounds():
    df = pd.DataFrame({"age": [30, 65], "female": [1, 0], "fam_dm": [0, 1], "dx_htn": [0, 1],
                       "bp_meds": [0, 1], "bmi": [22, 41]})
    assert ada_risk_score(df).tolist() == [0, 9]


def test_budget_flags_expected_share():
    rng = np.random.default_rng(0)
    s, w = rng.random(5000), rng.uniform(1, 3, 5000)
    f = flag_at_budget(s, w, 0.2)
    assert abs(np.sum(w * f) / w.sum() - 0.2) < 0.01


def test_operating_point_perfect_ranker():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0.0])
    op = operating_point(y, y, np.ones(10))
    assert op["sensitivity"] == 1 and op["ppv"] == 1 and op["share_flagged"] == pytest.approx(0.2)


@pytest.fixture(scope="module")
def data():
    return (add_phenotypes(load_cycle(C.TRAIN_CYCLE, synthetic=True)),
            add_phenotypes(load_cycle(C.TEST_CYCLE, synthetic=True)))


def test_harmonize_handles_renamed_bp_med_question(data):
    train, test = data
    # BPQ050A in 2017-2020, BPQ150 in 2021-2023 -> both map to bp_meds
    assert train["bp_meds"].sum() > 0 and test["bp_meds"].sum() > 0


def test_cohorts_exclude_diagnosed(data):
    _, test = data
    for t in TASKS:
        c = t.cohort(test)
        assert (c["age"] >= 20).all() and (c["pregnant"] != 1).all()
        if t.condition == "diabetes":
            assert (c["dx_diabetes"] != 1).all()
        else:
            assert (c["dx_kidney"] != 1).all()
    assert (TASKS[3].cohort(test)["egfr"] >= 60).all()


def test_end_to_end_task_and_forecast(data):
    train, test = data
    task = TASKS[0]
    res, preds = run_task(task, train, test, n_boot=20)
    auc = res["test"][res["chosen_model"]]["auroc"]
    assert 0.5 < auc <= 1.0
    assert {"y", "p", "reasons"} <= set(preds.columns)
    f = forecast(task, preds, "ADA risk test (>=5)", "all", n_sims=50)
    assert f["summary"]["tests_ordered"]["p50"] == pytest.approx(
        C.IMPACT["panel_size"] * 0.2 * C.IMPACT["test_completion"][1], rel=0.15)
