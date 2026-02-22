# Prostate CV training — debugging (same structure as cervical)

This mirrors the cervical CV debugging guide for the **prostate** pipeline.

## Script and data

- **CV script:** `train_prostate_cv.py` — RepeatedStratifiedKFold, one print per fold, results in `cv_results/prostate_cv_results.json`.
- **Data:** `data/Prostate_Cancer.csv` (auto-downloaded or placed manually). Target: `diagnosis_result` (M=1, B=0); 8 features (radius, texture, perimeter, area, smoothness, compactness, symmetry, fractal_dimension).
- **Sample size:** ~100; class balance often near 50/50.

## Same issues as cervical

- **Infinite loop:** Ensure a single `for fold_idx, (train_idx, test_idx) in enumerate(rskf.split(X_scaled, y))` with no `while True` wrapping it.
- **Same numbers every line:** Check that you’re not printing inside an XGBoost callback or an inner loop; print once per fold after evaluation.
- **Splits not changing:** Use `shuffle=True` and fixed `random_state` in RepeatedStratifiedKFold; load X, y once before the loop.

## Correct loop pattern

```python
rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=42, shuffle=True)
for fold_idx, (train_idx, test_idx) in enumerate(rskf.split(X_scaled, y)):
    X_tr, y_tr = X_scaled[train_idx], y.iloc[train_idx]
    X_te, y_te = X_scaled[test_idx], y.iloc[test_idx]
    clf.fit(X_tr, y_tr)
    # ... evaluate, print once
```

## Run

```bash
python train_prostate_cv.py
```

Expect a finite number of fold lines (e.g. 10), then aggregate metrics and saved JSON.
