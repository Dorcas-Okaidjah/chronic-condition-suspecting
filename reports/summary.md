# Results: Undiagnosed Chronic Condition Suspecting

Train: NHANES 2017-March 2020. Test: NHANES August 2021-August 2023 (temporal external validation). All rates are survey-weighted to the US adult population.

- dm_visit: features dropped by the schema-drift guard: fam_dm
- dm_bmp: features dropped by the schema-drift guard: fam_dm
- ckd_visit: features dropped by the schema-drift guard: fam_dm
- alb_bmp: features dropped by the schema-drift guard: fam_dm

## Discrimination and calibration (test cycle)

| Task | n (cases) | Prevalence | Model | AUROC (95% CI) | AUPRC | O/E | Cal. slope | Train CV AUROC |
|---|---|---|---|---|---|---|---|---|
| dm_visit | 4,911 (152) | 2.5% | logistic | 0.816 (0.772 to 0.856) | 0.123 | 0.85 | 0.80 | 0.830 |
| dm_bmp | 4,665 (146) | 2.6% | logistic | 0.940 (0.916 to 0.962) | 0.550 | 0.78 | 0.96 | 0.908 |
| ckd_visit | 5,118 (791) | 12.6% | logistic | 0.783 (0.756 to 0.807) | 0.381 | 1.02 | 1.11 | 0.750 |
| alb_bmp | 4,778 (451) | 8.1% | logistic | 0.751 (0.712 to 0.789) | 0.298 | 0.91 | 1.03 | 0.706 |

Effect of survey weights on calibration (observed/expected on the test cycle; 1.00 = perfect):

- dm_visit: unweighted training O/E 0.64 -> survey-weighted O/E 0.85
- dm_bmp: unweighted training O/E 0.64 -> survey-weighted O/E 0.78
- ckd_visit: unweighted training O/E 0.92 -> survey-weighted O/E 1.02
- alb_bmp: unweighted training O/E 0.85 -> survey-weighted O/E 0.91

Guideline AUROC on the same test patients:

- dm_visit / ADA risk test (>=5): AUROC 0.767; model minus guideline 0.009 to 0.093
- dm_visit / USPSTF age 35-70 & BMI>=25: AUROC 0.733; model minus guideline 0.030 to 0.135
- dm_bmp / ADA risk test (>=5): AUROC 0.765; model minus guideline 0.132 to 0.219
- dm_bmp / USPSTF age 35-70 & BMI>=25: AUROC 0.729; model minus guideline 0.166 to 0.254
- dm_bmp / Random glucose >=140 mg/dL: AUROC 0.921; model minus guideline -0.003 to 0.048
- ckd_visit / Guideline risk factor (any of DM/HTN/CVD/age>=60): AUROC 0.751; model minus guideline 0.020 to 0.044
- alb_bmp / Guideline risk factor (any of DM/HTN/CVD/age>=60): AUROC 0.707; model minus guideline 0.018 to 0.071

## Model vs. guideline at the same testing volume

| Task | Guideline | Share tested | Cases found: guideline | Cases found: model | Difference (95% CI) | PPV guideline | PPV model |
|---|---|---|---|---|---|---|---|
| dm_visit | ADA risk test (>=5) | 27.1% | 62.8% | 70.7% | -2.4% to 20.0% | 5.9% | 6.7% |
| dm_visit | USPSTF age 35-70 & BMI>=25 | 43.5% | 67.9% | 86.2% | 5.9% to 31.2% | 4.0% | 5.1% |
| dm_bmp | ADA risk test (>=5) | 27.1% | 62.6% | 95.1% | 22.7% to 43.0% | 5.9% | 9.0% |
| dm_bmp | USPSTF age 35-70 & BMI>=25 | 43.9% | 67.9% | 97.6% | 20.9% to 39.4% | 4.0% | 5.7% |
| dm_bmp | Random glucose >=140 mg/dL | 1.4% | 41.9% | 33.5% | -12.5% to -0.7% | 75.0% | 60.0% |
| ckd_visit | Guideline risk factor (any of DM/HTN/CVD/age>=60) | 47.3% | 80.2% | 82.7% | 0.1% to 5.3% | 21.3% | 22.0% |
| alb_bmp | Guideline risk factor (any of DM/HTN/CVD/age>=60) | 45.1% | 74.1% | 76.7% | -1.3% to 6.8% | 13.4% | 13.8% |

## Alert-budget operating points (model)

| Task | Flag top | Sensitivity (95% CI) | PPV (95% CI) | Tests per case found | Lift |
|---|---|---|---|---|---|
| dm_visit | 5% | 30.9% (21.6% to 38.4%) | 15.8% (10.3% to 20.4%) | 6.3 | 6.2x |
| dm_visit | 10% | 43.5% (34.0% to 53.3%) | 11.1% (8.1% to 14.3%) | 9.0 | 4.3x |
| dm_visit | 20% | 63.0% (53.3% to 73.0%) | 8.0% (6.3% to 10.0%) | 12.5 | 3.1x |
| dm_visit | 30% | 77.4% (68.9% to 85.5%) | 6.6% (5.2% to 8.1%) | 15.2 | 2.6x |
| dm_bmp | 5% | 68.5% (59.0% to 75.6%) | 35.1% (26.7% to 42.8%) | 2.8 | 13.6x |
| dm_bmp | 10% | 80.3% (73.2% to 87.3%) | 20.5% (16.0% to 25.7%) | 4.9 | 8.0x |
| dm_bmp | 20% | 89.7% (84.6% to 96.0%) | 11.5% (9.3% to 14.3%) | 8.7 | 4.5x |
| dm_bmp | 30% | 97.0% (93.9% to 99.5%) | 8.3% (6.8% to 10.2%) | 12.0 | 3.2x |
| ckd_visit | 5% | 20.7% (18.4% to 23.3%) | 51.9% (45.7% to 58.5%) | 1.9 | 4.1x |
| ckd_visit | 10% | 35.2% (31.9% to 38.4%) | 44.2% (39.6% to 48.4%) | 2.3 | 3.5x |
| ckd_visit | 20% | 54.7% (50.5% to 58.7%) | 34.3% (31.0% to 37.5%) | 2.9 | 2.7x |
| ckd_visit | 30% | 68.3% (63.8% to 72.5%) | 28.6% (25.9% to 31.0%) | 3.5 | 2.3x |
| alb_bmp | 5% | 24.7% (20.9% to 29.6%) | 40.0% (33.3% to 48.2%) | 2.5 | 4.9x |
| alb_bmp | 10% | 36.8% (32.4% to 42.5%) | 30.0% (26.0% to 35.3%) | 3.3 | 3.7x |
| alb_bmp | 20% | 56.4% (50.7% to 62.7%) | 22.9% (20.1% to 26.0%) | 4.4 | 2.8x |
| alb_bmp | 30% | 69.0% (63.3% to 74.6%) | 18.7% (16.6% to 21.1%) | 5.3 | 2.3x |

## dm_bmp: hybrid (lab rule first, then model) vs. model alone

| Flag top | Model sensitivity | Hybrid sensitivity | Hybrid minus model (95% CI) |
|---|---|---|---|
| 5% | 68.5% | 69.5% | -3.2% to 3.8% |
| 10% | 80.3% | 80.3% | 0.0% to 0.0% |
| 20% | 89.7% | 89.7% | 0.0% to 0.0% |
| 30% | 97.0% | 97.0% | 0.0% to 0.0% |

## Impact forecast per 10,000-adult panel (median [P10, P90])

Capacity: outreach testing for 20% of the panel. Guideline = test guideline-eligible patients (random draw if more are eligible than capacity); model = test top-ranked. Assumptions and ranges are in `src/ccs/config.py`.

| Task | Population | vs. guideline | Tests (model) | Extra confirmed dx | P(extra > 0) | Lab $ per dx: model / guideline | Annual RAF value of extra dx |
|---|---|---|---|---|---|---|---|
| dm_visit | all | ADA risk test (>=5) | 1,204 [982, 1,426] | 21.0 [12.4, 31.4] | 100% | $199 / $271 | - |
| dm_visit | 65+ | ADA risk test (>=5) | 1,201 [987, 1,407] | 53.9 [31.9, 78.0] | 100% | $142 / $275 | $106,410 [$62,686, $155,770] |
| dm_bmp | all | ADA risk test (>=5) | 1,205 [984, 1,415] | 56.3 [41.8, 73.2] | 100% | $136 / $268 | - |
| dm_bmp | 65+ | ADA risk test (>=5) | 1,203 [978, 1,413] | 116.5 [85.3, 155.0] | 100% | $90 / $263 | $231,547 [$167,610, $313,883] |
| ckd_visit | all | Guideline risk factor (any of DM/HTN/CVD/age>=60) | 1,207 [989, 1,421] | 129.2 [102.4, 158.7] | 100% | $46 / $74 | - |
| ckd_visit | 65+ | Guideline risk factor (any of DM/HTN/CVD/age>=60) | 1,209 [987, 1,421] | 222.3 [170.0, 288.2] | 100% | $30 / $53 | $161,311 [$104,850, $225,580] |
| alb_bmp | all | Guideline risk factor (any of DM/HTN/CVD/age>=60) | 1,206 [984, 1,420] | 95.1 [74.7, 118.4] | 100% | $69 / $118 | - |
| alb_bmp | 65+ | Guideline risk factor (any of DM/HTN/CVD/age>=60) | 1,205 [972, 1,429] | 155.9 [112.4, 210.0] | 100% | $50 / $101 | $0 [$0, $0] |

## Subgroup audit (flag top 20%)

| Task | Group | n (cases) | Prevalence | Sensitivity | PPV | O/E |
|---|---|---|---|---|---|---|
| dm_visit | sex: Female | 2,727 (76) | 2.1% | 74.1% | 7.4% | 0.69 |
| dm_visit | sex: Male | 2,184 (76) | 3.0% | 54.4% | 8.8% | 1.04 |
| dm_visit | race_ethnicity: Hispanic | 812 (33) | 3.3% | 65.8% | 11.2% | 1.22 |
| dm_visit | race_ethnicity: NH Asian * | 277 (12) | 3.3% | 57.9% | 12.3% | 1.43 |
| dm_visit | race_ethnicity: NH Black | 541 (29) | 4.8% | 53.9% | 9.6% | 1.15 |
| dm_visit | race_ethnicity: NH White | 2,985 (74) | 2.1% | 64.8% | 6.7% | 0.69 |
| dm_visit | race_ethnicity: Other/Multi * | 296 (4) | 0.9% | 89.1% | 5.6% | 0.33 |
| dm_visit | age: 20-44 | 1,783 (25) | 1.2% | 38.2% | 6.6% | 1.00 |
| dm_visit | age: 45-64 | 1,633 (59) | 3.4% | 66.6% | 8.5% | 0.83 |
| dm_visit | age: 65+ | 1,495 (68) | 4.4% | 74.5% | 8.1% | 0.79 |
| dm_visit | income: PIR<1.3 (low income) | 869 (29) | 2.5% | 53.7% | 7.0% | 0.84 |
| dm_visit | income: PIR>=1.3 | 3,417 (105) | 2.6% | 63.5% | 8.3% | 0.87 |
| dm_visit | income: Unknown * | 625 (18) | 2.4% | 70.8% | 7.7% | 0.76 |
| dm_bmp | sex: Female | 2,580 (73) | 2.2% | 88.3% | 9.5% | 0.68 |
| dm_bmp | sex: Male | 2,085 (73) | 3.0% | 90.7% | 13.7% | 0.88 |
| dm_bmp | race_ethnicity: Hispanic | 769 (32) | 3.2% | 92.1% | 15.1% | 0.87 |
| dm_bmp | race_ethnicity: NH Asian * | 262 (10) | 3.0% | 100.0% | 15.8% | 0.91 |
| dm_bmp | race_ethnicity: NH Black | 503 (26) | 4.7% | 82.2% | 15.2% | 1.43 |
| dm_bmp | race_ethnicity: NH White | 2,861 (74) | 2.2% | 91.4% | 10.0% | 0.67 |
| dm_bmp | race_ethnicity: Other/Multi * | 270 (4) | 1.0% | 49.7% | 3.1% | 0.33 |
| dm_bmp | age: 20-44 | 1,693 (25) | 1.3% | 80.7% | 14.4% | 0.85 |
| dm_bmp | age: 45-64 | 1,554 (55) | 3.3% | 92.0% | 11.6% | 0.78 |
| dm_bmp | age: 65+ | 1,418 (66) | 4.5% | 92.9% | 10.3% | 0.73 |
| dm_bmp | income: PIR<1.3 (low income) | 800 (28) | 2.6% | 83.3% | 11.9% | 1.00 |
| dm_bmp | income: PIR>=1.3 | 3,272 (101) | 2.6% | 89.2% | 11.5% | 0.76 |
| dm_bmp | income: Unknown * | 593 (17) | 2.4% | 100.0% | 11.3% | 0.68 |
| ckd_visit | sex: Female | 2,796 (408) | 13.0% | 58.2% | 30.8% | 0.92 |
| ckd_visit | sex: Male | 2,322 (383) | 12.1% | 50.7% | 40.3% | 1.16 |
| ckd_visit | race_ethnicity: Hispanic | 875 (106) | 9.3% | 40.2% | 24.0% | 0.87 |
| ckd_visit | race_ethnicity: NH Asian | 285 (41) | 13.1% | 47.6% | 44.6% | 1.26 |
| ckd_visit | race_ethnicity: NH Black | 587 (134) | 18.5% | 58.5% | 39.9% | 1.27 |
| ckd_visit | race_ethnicity: NH White | 3,063 (457) | 12.3% | 57.4% | 33.9% | 0.98 |
| ckd_visit | race_ethnicity: Other/Multi | 308 (53) | 14.3% | 55.4% | 42.3% | 1.19 |
| ckd_visit | age: 20-44 | 1,704 (87) | 5.0% | 9.4% | 47.9% | 0.98 |
| ckd_visit | age: 45-64 | 1,781 (225) | 11.7% | 45.4% | 26.2% | 0.87 |
| ckd_visit | age: 65+ | 1,633 (479) | 29.8% | 76.6% | 38.3% | 1.17 |
| ckd_visit | income: PIR<1.3 (low income) | 896 (156) | 13.8% | 57.7% | 37.7% | 1.08 |
| ckd_visit | income: PIR>=1.3 | 3,575 (512) | 11.8% | 52.9% | 31.8% | 0.97 |
| ckd_visit | income: Unknown | 647 (123) | 15.3% | 58.5% | 43.1% | 1.22 |
| alb_bmp | sex: Female | 2,612 (224) | 8.3% | 55.4% | 18.2% | 0.82 |
| alb_bmp | sex: Male | 2,166 (227) | 8.0% | 57.5% | 31.3% | 1.04 |
| alb_bmp | race_ethnicity: Hispanic | 846 (77) | 7.8% | 57.7% | 22.8% | 0.84 |
| alb_bmp | race_ethnicity: NH Asian | 274 (30) | 10.2% | 64.9% | 33.4% | 1.12 |
| alb_bmp | race_ethnicity: NH Black | 524 (71) | 10.7% | 63.4% | 24.0% | 1.01 |
| alb_bmp | race_ethnicity: NH White | 2,844 (238) | 7.4% | 52.3% | 20.5% | 0.87 |
| alb_bmp | race_ethnicity: Other/Multi | 290 (35) | 10.8% | 62.0% | 33.4% | 1.13 |
| alb_bmp | age: 20-44 | 1,701 (84) | 4.9% | 38.7% | 31.8% | 0.82 |
| alb_bmp | age: 45-64 | 1,720 (164) | 8.5% | 60.1% | 19.1% | 0.80 |
| alb_bmp | age: 65+ | 1,357 (203) | 15.7% | 66.6% | 24.3% | 1.20 |
| alb_bmp | income: PIR<1.3 (low income) | 832 (92) | 9.1% | 64.7% | 26.3% | 0.91 |
| alb_bmp | income: PIR>=1.3 | 3,357 (294) | 7.7% | 51.6% | 20.2% | 0.90 |
| alb_bmp | income: Unknown | 589 (65) | 9.3% | 68.4% | 33.8% | 0.99 |

\* fewer than 20 cases: treat as directional only.
