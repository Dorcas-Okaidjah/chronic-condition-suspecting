"""Project configuration: NHANES file specs, phenotype thresholds, and impact assumptions.

Everything a reviewer might want to challenge lives here, in one place.
"""

# ---------------------------------------------------------------------------
# NHANES cycles
#   train = 2017-March 2020 pre-pandemic (P_ files)
#   test  = August 2021-August 2023 (_L files)  -> temporal external validation
# ---------------------------------------------------------------------------
NHANES_BASE = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{file}.xpt"

# logical component -> file name per cycle
CYCLES = {
    "2017-2020": {
        "year": 2017,
        "files": {
            "demo": "P_DEMO", "ghb": "P_GHB", "diq": "P_DIQ", "biopro": "P_BIOPRO",
            "alb_cr": "P_ALB_CR", "kiq": "P_KIQ_U", "bmx": "P_BMX", "bpxo": "P_BPXO",
            "bpq": "P_BPQ", "mcq": "P_MCQ", "smq": "P_SMQ",
        },
        "weight_col": "WTMECPRP",
    },
    "2021-2023": {
        "year": 2021,
        "files": {
            "demo": "DEMO_L", "ghb": "GHB_L", "diq": "DIQ_L", "biopro": "BIOPRO_L",
            "alb_cr": "ALB_CR_L", "kiq": "KIQ_U_L", "bmx": "BMX_L", "bpxo": "BPXO_L",
            "bpq": "BPQ_L", "mcq": "MCQ_L", "smq": "SMQ_L",
        },
        "weight_col": "WTMEC2YR",
    },
}
TRAIN_CYCLE = "2017-2020"
TEST_CYCLE = "2021-2023"

# ---------------------------------------------------------------------------
# Phenotype thresholds (single-visit, survey definitions -- see README limitations)
# ---------------------------------------------------------------------------
HBA1C_DIABETES = 6.5      # % ; ADA diagnostic threshold
EGFR_CKD = 60.0           # mL/min/1.73m2 ; CKD-EPI 2021 (race-free)
UACR_CKD = 30.0           # mg/g ; moderately increased albuminuria (A2+)
EGFR_STAGE3_LOW = 30.0    # eGFR 30-59 -> CKD stage 3 (payment-relevant in CMS-HCC V28)
MIN_AGE = 20

# ---------------------------------------------------------------------------
# Feature sets.  Race/ethnicity and income are deliberately NOT model inputs;
# they are used only to audit performance across groups.
# ---------------------------------------------------------------------------
VISIT_FEATURES = [
    "age", "female", "bmi", "waist", "sbp", "dbp",
    "dx_htn", "bp_meds", "dx_chol", "cvd", "fam_dm",
    "smoke_now", "smoke_ever",
]
BMP_FEATURES = ["glucose_serum", "egfr"]   # routinely on a basic metabolic panel

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
ALERT_BUDGETS = [0.05, 0.10, 0.20, 0.30]   # share of eligible patients flagged
N_BOOTSTRAP = 500
RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# Impact-forecast assumptions.  Every value is an ASSUMPTION with a range used
# in the Monte Carlo; override them for a real plan.
#   (low, mode, high) -> triangular distribution
# ---------------------------------------------------------------------------
IMPACT = {
    "panel_size": 10_000,                       # adult patients in a PCP panel
    "test_completion": (0.40, 0.60, 0.80),      # flagged patients who complete the lab
    "confirm_and_document": (0.70, 0.85, 0.95), # true positives confirmed & coded at follow-up
    "lab_cost_usd": {"hba1c": (8, 12, 20), "uacr": (8, 12, 20)},
    # CMS-HCC V28, community non-dual aged reference coefficients (PY2026):
    #   HCC 38 diabetes w/ glycemic, unspecified or no complications = 0.166
    #   HCC 329 CKD moderate (stage 3, except 3B) = 0.127
    # Only stage 3+ CKD maps to a payment HCC; albuminuria-only CKD (stage 1-2) does not.
    "raf": {"diabetes": 0.166, "ckd_stage3": 0.127},
    "usd_per_raf_year": (10_000, 12_000, 14_000),  # annual MA payment per 1.0 RAF (assumption)
}
