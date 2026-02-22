# Prostate Cancer Risk Stratification — Full Guide

This mirrors the cervical risk stratification guide for the **prostate** dataset (~100 samples, 8 features, diagnosis M/B).

---

## 1. Pipeline and scripts

| Component | Cervical | Prostate |
|-----------|----------|----------|
| CV training | `train_cervical_cv.py` | `train_prostate_cv.py` |
| Full stratification | `cervical_risk_stratification.py` | `prostate_risk_stratification.py` |
| Results | `cv_results/cervical_cv_results.json` | `cv_results/prostate_cv_results.json` |
| Stratification output | `stratification_results/<timestamp>/` | `stratification_results/prostate/<timestamp>/` |
| Triage utilities | `clinical_triage.py` (shared) | Same |

---

## 2. Prostate-specific notes

- **Sample size:** ~100 — use stratified CV (e.g. 5×2); bootstrap CIs use `min_valid_samples=50`. SMOTE is optional and only applied when positives are few (e.g. &lt; 45).
- **Features:** 8 (radius, texture, perimeter, area, smoothness, compactness, symmetry, fractal_dimension). VarianceThreshold(0.01) may keep all; if none pass, script falls back to all features.
- **Calibration:** Same as cervical — inner 75/25 split per outer fold; isotonic or sigmoid. With ~50 positives, calibration is more stable than with 6% prevalence.
- **Risk tiers:** Same boundaries (0–0.1, 0.1–0.25, 0.25–0.5, 0.5–1.0). Tier counts must sum to **number of patients** (one out-of-fold prediction per patient).
- **Recall@k, NNS:** Implemented in `prostate_risk_stratification.py` via `clinical_triage`; reported in `summary.json`.

---

## 3. Run commands

```bash
# CV only
python train_prostate_cv.py

# Full stratification (nested CV, calibration, tiers, bootstrap, recall@k, NNS, plots)
python prostate_risk_stratification.py
```

---

## 4. Outputs

- `stratification_results/prostate/<timestamp>/summary.json` — metrics, risk_tiers, recall_at_20pct_intervention, nns_at_top20pct, bootstrap meta.
- `calibration_curve.png`, `risk_tiers.png`, `decision_curve.png`, `feature_importance.png`.

---

## 5. Clinical triage

Use the **same** `clinical_triage.py` for prostate: `triage_patient(patient_features, model_pipeline, ...)` and `format_clinical_report(patient_id, triage_result)`. Use prostate prevalence (e.g. ~0.5 if 50/50) for `prevalence_baseline` if desired. See `docs/PROSTATE_CLINICAL_TRIAGE_GUIDE.md`.
