"""Download, cache and harmonize NHANES files into one analysis table per cycle.

Raw NHANES variables are mapped to plain names (age, hba1c, uacr, ...).  Any file or
column that is missing in a cycle is reported and filled with NaN rather than crashing,
because NHANES questionnaires change between cycles (e.g. BP-medication question
BPQ050A -> BPQ150 in 2021-2023).
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)
RAW_DIR = Path("data/raw")


# ---------------------------------------------------------------------------
# Download / read
# ---------------------------------------------------------------------------
def _download(url: str, dest: Path) -> None:
    import requests  # imported lazily so tests run without network deps

    headers = {"User-Agent": "Mozilla/5.0 (research; chronic-condition-suspecting)"}
    r = requests.get(url, headers=headers, timeout=120)
    r.raise_for_status()
    if r.content[:6] in (b"<!DOCT", b"<html>", b"<HTML>"):
        raise ValueError(f"Got an HTML page instead of an XPT file from {url}")
    dest.write_bytes(r.content)


def load_raw_tables(cycle: str, raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Return {component: DataFrame} for one cycle, downloading files on first use."""
    spec = config.CYCLES[cycle]
    raw_dir.mkdir(parents=True, exist_ok=True)
    tables = {}
    for comp, fname in spec["files"].items():
        path = raw_dir / f"{fname}.xpt"
        url = config.NHANES_BASE.format(year=spec["year"], file=fname)
        try:
            if not path.exists():
                log.info("downloading %s", url)
                _download(url, path)
            df = pd.read_sas(path, format="xport", encoding="latin-1")
            df["SEQN"] = df["SEQN"].astype(int)
            tables[comp] = df
        except Exception as exc:  # noqa: BLE001 - report and continue
            log.warning("could not load %s (%s): %s", fname, cycle, exc)
    return tables


# ---------------------------------------------------------------------------
# Harmonize
# ---------------------------------------------------------------------------
def _yes_no(s: pd.Series) -> pd.Series:
    """NHANES 1=yes, 2=no, 7/9=refused/don't know -> 1.0 / 0.0 / NaN."""
    return s.map({1: 1.0, 2: 0.0})


def _col(df: pd.DataFrame, *candidates: str) -> pd.Series:
    for c in candidates:
        if c in df.columns:
            return df[c]
    return pd.Series(np.nan, index=df.index)


def ckd_epi_2021(scr: pd.Series, age: pd.Series, female: pd.Series) -> pd.Series:
    """Race-free CKD-EPI 2021 creatinine equation (mL/min/1.73m^2)."""
    kappa = np.where(female == 1, 0.7, 0.9)
    alpha = np.where(female == 1, -0.241, -0.302)
    ratio = scr / kappa
    egfr = (142 * np.minimum(ratio, 1) ** alpha * np.maximum(ratio, 1) ** -1.200
            * 0.9938 ** age * np.where(female == 1, 1.012, 1.0))
    return pd.Series(egfr, index=scr.index)


def harmonize(tables: dict[str, pd.DataFrame], cycle: str) -> pd.DataFrame:
    if "demo" not in tables:
        raise RuntimeError(f"DEMO file missing for {cycle}; cannot build cohort")
    df = tables["demo"].copy()
    for comp, t in tables.items():
        if comp != "demo":
            df = df.merge(t, on="SEQN", how="left", suffixes=("", f"_{comp}"))

    out = pd.DataFrame({"seqn": df["SEQN"], "cycle": cycle})
    out["age"] = df["RIDAGEYR"]
    out["female"] = (df["RIAGENDR"] == 2).astype(float)
    out["race"] = df["RIDRETH3"].map({
        1: "Hispanic", 2: "Hispanic", 3: "NH White", 4: "NH Black",
        6: "NH Asian", 7: "Other/Multi"})
    out["pir"] = _col(df, "INDFMPIR")
    out["weight"] = _col(df, config.CYCLES[cycle]["weight_col"])
    out["pregnant"] = (_col(df, "RIDEXPRG") == 1).astype(float)

    # labs
    out["hba1c"] = _col(df, "LBXGH")
    out["scr"] = _col(df, "LBXSCR")
    out["glucose_serum"] = _col(df, "LBXSGL")
    out["uacr"] = _col(df, "URDACT")
    out["egfr"] = ckd_epi_2021(out["scr"], out["age"], out["female"])

    # exam
    out["bmi"] = _col(df, "BMXBMI")
    out["waist"] = _col(df, "BMXWAIST")
    sys_cols = [c for c in ("BPXOSY1", "BPXOSY2", "BPXOSY3") if c in df]
    dia_cols = [c for c in ("BPXODI1", "BPXODI2", "BPXODI3") if c in df]
    out["sbp"] = df[sys_cols].mean(axis=1) if sys_cols else np.nan
    out["dbp"] = df[dia_cols].mean(axis=1) if dia_cols else np.nan

    # questionnaire (what a PCP would know from the chart / history)
    out["dx_diabetes"] = _yes_no(_col(df, "DIQ010"))
    out["dx_prediabetes"] = _yes_no(_col(df, "DIQ160"))
    out["dx_kidney"] = _yes_no(_col(df, "KIQ022"))
    out["dx_htn"] = _yes_no(_col(df, "BPQ020"))
    out["bp_meds"] = _yes_no(_col(df, "BPQ150", "BPQ050A")).fillna(0.0)
    out["dx_chol"] = _yes_no(_col(df, "BPQ080"))
    cvd_items = [_yes_no(_col(df, c)) for c in ("MCQ160B", "MCQ160C", "MCQ160E", "MCQ160F")]
    out["cvd"] = pd.concat(cvd_items, axis=1).max(axis=1)
    out["fam_dm"] = _yes_no(_col(df, "MCQ300C"))
    out["smoke_ever"] = _yes_no(_col(df, "SMQ020"))
    out["smoke_now"] = _col(df, "SMQ040").map({1: 1.0, 2: 1.0, 3: 0.0})
    out.loc[out["smoke_ever"] == 0, "smoke_now"] = 0.0

    missing = [c for c in out.columns if out[c].isna().all()]
    if missing:
        log.warning("[%s] variables entirely missing (check NHANES docs): %s", cycle, missing)
    return out


def load_cycle(cycle: str, synthetic: bool = False, seed: int = 0) -> pd.DataFrame:
    tables = synthetic_raw_tables(cycle, seed=seed) if synthetic else load_raw_tables(cycle)
    return harmonize(tables, cycle)


# ---------------------------------------------------------------------------
# Synthetic NHANES-shaped data (for tests / CI only -- never for results)
# ---------------------------------------------------------------------------
def synthetic_raw_tables(cycle: str, n: int = 6000, seed: int = 0) -> dict[str, pd.DataFrame]:
    """Fake raw tables with real NHANES column names, so the full harmonize path runs."""
    rng = np.random.default_rng(seed + (0 if cycle == config.TRAIN_CYCLE else 1))
    spec = config.CYCLES[cycle]
    seqn = np.arange(n) + (100_000 if cycle == config.TRAIN_CYCLE else 200_000)
    age = rng.integers(12, 81, n)
    sex = rng.integers(1, 3, n)
    bmi = np.clip(rng.normal(29.5, 6.5, n), 16, 65)
    htn_latent = -4.5 + 0.06 * age + 0.06 * bmi + rng.normal(0, 1, n)
    sbp = 105 + 0.45 * age + 0.4 * bmi + rng.normal(0, 12, n)
    dm_latent = -9.0 + 0.055 * age + 0.11 * bmi + 0.4 * (sex == 1) + rng.normal(0, 1.1, n)
    has_dm = dm_latent > 0
    aware = rng.random(n) < 0.75
    a1c = np.where(has_dm, rng.normal(7.4, 1.0, n), rng.normal(5.4, 0.35, n))
    gluc = 70 + 9 * (a1c - 4.5) + rng.normal(0, 12, n)
    scr_base = np.where(sex == 2, 0.72, 0.95) * (1 + 0.006 * np.maximum(age - 40, 0))
    scr = scr_base * np.exp(rng.normal(0, 0.18, n) + 0.25 * has_dm * rng.random(n))
    uacr = np.exp(rng.normal(2.0, 1.0, n) + 0.9 * has_dm + 0.02 * np.maximum(sbp - 120, 0))

    def yn(p):
        return np.where(rng.random(n) < p, 1, 2)

    demo = pd.DataFrame({"SEQN": seqn, "RIDAGEYR": age, "RIAGENDR": sex,
                         "RIDRETH3": rng.choice([1, 2, 3, 4, 6, 7], n, p=[.1, .08, .55, .12, .07, .08]),
                         "INDFMPIR": np.round(rng.uniform(0, 5, n), 2),
                         spec["weight_col"]: rng.uniform(5_000, 80_000, n),
                         "RIDEXPRG": np.where((sex == 2) & (rng.random(n) < .02), 1, 2)})
    tables = {
        "demo": demo,
        "ghb": pd.DataFrame({"SEQN": seqn, "LBXGH": np.round(a1c, 1)}),
        "biopro": pd.DataFrame({"SEQN": seqn, "LBXSCR": np.round(scr, 2), "LBXSGL": np.round(gluc)}),
        "alb_cr": pd.DataFrame({"SEQN": seqn, "URDACT": np.round(uacr, 2)}),
        "bmx": pd.DataFrame({"SEQN": seqn, "BMXBMI": bmi, "BMXWAIST": 40 + 2.2 * bmi + rng.normal(0, 6, n)}),
        "bpxo": pd.DataFrame({"SEQN": seqn, **{f"BPXOSY{i}": sbp + rng.normal(0, 4, n) for i in (1, 2, 3)},
                              **{f"BPXODI{i}": 0.55 * sbp + 5 + rng.normal(0, 5, n) for i in (1, 2, 3)}}),
        "diq": pd.DataFrame({"SEQN": seqn, "DIQ010": np.where(has_dm & aware, 1, 2),
                             "DIQ160": yn(0.12)}),
        "kiq": pd.DataFrame({"SEQN": seqn, "KIQ022": yn(0.03)}),
        "bpq": pd.DataFrame({"SEQN": seqn, "BPQ020": np.where(htn_latent > 0.5, 1, 2),
                             ("BPQ050A" if cycle == config.TRAIN_CYCLE else "BPQ150"):
                                 np.where(htn_latent > 0.8, 1, 2),
                             "BPQ080": yn(0.3)}),
        "mcq": pd.DataFrame({"SEQN": seqn, **{c: yn(0.02 + 0.001 * age) for c in
                                              ("MCQ160B", "MCQ160C", "MCQ160E", "MCQ160F")},
                             "MCQ300C": np.where(rng.random(n) < 0.3 + 0.15 * has_dm, 1, 2)}),
        "smq": pd.DataFrame({"SEQN": seqn, "SMQ020": yn(0.4), "SMQ040": rng.choice([1, 2, 3], n)}),
    }
    return tables
