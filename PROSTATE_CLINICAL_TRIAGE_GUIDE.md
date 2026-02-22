# Prostate Cancer Risk Stratification — Clinical Triage Guide

Same structure as the cervical clinical triage guide; adapted for **prostate** (e.g. ~100 samples, M/B diagnosis, 8 imaging/measurement features).

---

## 1. Calibration and probabilities

- **Prostate** often has near 50/50 class balance, so calibration can be more stable than with 6% prevalence. Still fit the calibrator on an **inner holdout** (25% of outer train); never use test data.
- Use **isotonic** or **sigmoid** (Platt); compare Brier score. With ~50 positives in calibration, isotonic is usually fine.
- If probabilities are shifted, present **percentile-based** risk (“top 10% risk”) or **relative risk vs baseline** using `clinical_triage.percentile_risk_tier()` and `triage_patient(..., use_percentile=True)`.

---

## 2. Presenting risk to clinicians

- **Categories:** low / moderate / high (or high_risk / elevated / moderate / low_risk if using percentiles).
- **Action:** Routine screening vs follow-up vs biopsy per protocol. Same logic as cervical in `triage_patient()`.
- **Score:** Prefer “risk percentile” or “risk score 0–100” over “probability of cancer” when calibration is uncertain.
- **Baseline:** Use cohort prevalence (e.g. 0.5) for relative risk if relevant.

---

## 3. Thresholds and workload

- **Recall at 20%:** Use `recall_at_k(y_true, y_proba, k_fraction=0.20)` on **out-of-fold** prostate predictions (one per patient). Reported in `prostate_risk_stratification` summary.
- **NNS:** `number_needed_to_screen(y_true, y_proba, threshold)` at a chosen threshold (e.g. top 20%).
- Validate thresholds on the **single** set of OOF predictions so tier counts sum to sample size (e.g. 100).

---

## 4. Aggregation (no double-counting)

- Use **one prediction per patient** (out-of-fold from the fold where that patient was in test). `y_true_flat` and `y_proba_flat` in `prostate_risk_stratification.py` already do this. Risk tier counts must sum to **100** (or your N), not to folds × per-fold size.

---

## 5. Triage function (shared with cervical)

```python
from clinical_triage import triage_patient, format_clinical_report

# Prostate: one row of 8 features (same order as training)
result = triage_patient(
    patient_features,
    prostate_model_pipeline,
    prevalence_baseline=0.50,  # or your cohort prevalence
)
print(format_clinical_report("PATIENT_ID", result))
```

---

## 6. Validation metrics

- **ROC-AUC, PR-AUC** with bootstrap CIs (stratified).
- **Recall@10%, 20%, 30%** via `recall_at_k_curve`.
- **NNS** at top 20% (or chosen threshold).
- **Decision curve** (net benefit vs threshold) — produced by `prostate_risk_stratification.py`.

---

## 7. Communication and limitations

- Explain that the tool is for **triage**, not diagnosis; biopsy remains definitive.
- With ~100 patients, report **confidence intervals** and note small sample size.
- Use **same** guardrails as cervical: category + recommendation + disclaimer; avoid presenting raw probability as “probability of cancer” if uncalibrated.

---

## 8. Code reference

| Need | Where |
|------|--------|
| Triage one patient | `clinical_triage.triage_patient()` (same as cervical) |
| Recall at k% | `clinical_triage.recall_at_k()` |
| NNS | `clinical_triage.number_needed_to_screen()` |
| Risk tiers (OOF) | `clinical_triage.risk_tiers_from_oof_predictions()` or pipeline’s `risk_tier_analysis` |
| Percentile tier | `clinical_triage.percentile_risk_tier()` |
| Report text | `clinical_triage.format_clinical_report()` |
| Full prostate pipeline | `prostate_risk_stratification.py` |
