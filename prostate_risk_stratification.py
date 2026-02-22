"""
Prostate cancer risk stratification — full pipeline (mirror of cervical)
========================================================================
- Nested CV (outer = unbiased performance, inner = calibration)
- Optional SMOTE for imbalance; isotonic/Platt calibration
- Threshold optimization, risk tiers, bootstrap CIs
- Calibration curve with bands, decision curve, feature importance
- Recall@k, NNS, summary JSON
"""

import json
import urllib.request
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import VarianceThreshold
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    brier_score_loss,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.base import clone

warnings.filterwarnings("ignore")

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    xgb = None
    XGB_AVAILABLE = False
try:
    from imblearn.over_sampling import SMOTE
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    PLOT_AVAILABLE = True
except ImportError:
    PLOT_AVAILABLE = False
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(x, **kw): return x

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "stratification_results" / "prostate"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = OUT_DIR / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
N_OUTER_SPLITS = 5
N_OUTER_REPEATS = 2
N_BOOTSTRAP = 200
RISK_TIERS = (0.0, 0.10, 0.25, 0.50, 1.0)
PROSTATE_CSV_URL = "https://raw.githubusercontent.com/bikramb98/prostate-cancer-prediction/master/Prostate_Cancer.csv"
PROSTATE_TARGET = "diagnosis_result"
PROSTATE_FEATURES = [
    "radius", "texture", "perimeter", "area",
    "smoothness", "compactness", "symmetry", "fractal_dimension",
]


def download_prostate_data():
    path = DATA_DIR / "Prostate_Cancer.csv"
    if path.exists():
        return path
    try:
        req = urllib.request.Request(PROSTATE_CSV_URL, headers={"User-Agent": "GeneShield/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            path.write_bytes(resp.read())
        return path
    except Exception:
        return None


def load_prostate_data(csv_path=None):
    if csv_path is None:
        csv_path = DATA_DIR / "Prostate_Cancer.csv"
    if not Path(csv_path).exists():
        csv_path = download_prostate_data()
    if csv_path is None:
        raise FileNotFoundError("Prostate_Cancer.csv not in data/. Place it there or enable download.")
    df = pd.read_csv(csv_path)
    if PROSTATE_TARGET not in df.columns:
        raise KeyError(f"Target '{PROSTATE_TARGET}' not found")
    df[PROSTATE_TARGET] = df[PROSTATE_TARGET].map({"M": 1, "B": 0})
    df = df.dropna(subset=[PROSTATE_TARGET])
    y = df[PROSTATE_TARGET].astype(int)
    available = [f for f in PROSTATE_FEATURES if f in df.columns]
    X = df.loc[y.index, available].copy()
    return X, y, available


def get_base_clf(scale_pos_weight):
    if XGB_AVAILABLE:
        return xgb.XGBClassifier(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.05,
            scale_pos_weight=scale_pos_weight,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
        )
    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.05, random_state=RANDOM_STATE,
    )


def resample_train(X_tr, y_tr, k=2):
    if not IMBLEARN_AVAILABLE or y_tr.sum() < 2:
        return X_tr, y_tr
    n_pos = int(y_tr.sum())
    k = min(k, n_pos - 1) if n_pos <= 3 else 3
    try:
        smote = SMOTE(random_state=RANDOM_STATE, k_neighbors=k)
        X_r, y_r = smote.fit_resample(X_tr, y_tr)
        return X_r, y_r
    except Exception:
        return X_tr, y_tr


def optimize_threshold(y_true, y_proba):
    from sklearn.metrics import roc_curve
    fpr, tpr, thresh = roc_curve(y_true, y_proba)
    j = tpr - fpr
    idx = np.argmax(j)
    return thresh[idx], float(tpr[idx]), float(1 - fpr[idx])


def risk_tier_analysis(y_true, y_proba, tiers=RISK_TIERS):
    tiers = np.asarray(tiers)
    results = []
    total_pos = float((y_true == 1).sum())
    for i in range(len(tiers) - 1):
        lo, hi = tiers[i], tiers[i + 1]
        mask = (y_proba >= lo) & (y_proba < hi) if i < len(tiers) - 2 else (y_proba >= lo) & (y_proba <= hi)
        n = int(mask.sum())
        if n == 0:
            results.append({"bin": f"[{lo:.2f},{hi:.2f}]", "n": 0, "n_pos": 0, "recall": 0, "precision": 0})
            continue
        n_pos = int((y_true[mask] == 1).sum())
        prec = n_pos / n if n > 0 else 0
        rec = n_pos / total_pos if total_pos > 0 else 0
        results.append({"bin": f"[{lo:.2f},{hi:.2f}]", "n": n, "n_pos": n_pos, "recall": rec, "precision": prec})
    return results


def run_nested_cv(X, y, feature_names, use_smote=False, use_calibration="isotonic"):
    scale_pos = (y == 0).sum() / max((y == 1).sum(), 1)
    var_sel = VarianceThreshold(threshold=0.01)
    scaler = StandardScaler()
    X_var = var_sel.fit_transform(X)
    X_scaled = scaler.fit_transform(X_var)
    sel_names = [feature_names[i] for i in np.where(var_sel.get_support())[0]]
    if len(sel_names) == 0:
        sel_names = feature_names
        X_scaled = scaler.fit_transform(X)

    outer_cv = RepeatedStratifiedKFold(n_splits=N_OUTER_SPLITS, n_repeats=N_OUTER_REPEATS, random_state=RANDOM_STATE)
    outer_results = []
    all_y_true = []
    all_y_proba = []
    fold_models = []

    for fold_idx, (train_idx, test_idx) in enumerate(tqdm(list(outer_cv.split(X_scaled, y)), desc="Outer folds")):
        X_tr = X_scaled[train_idx]
        y_tr = y.iloc[train_idx]
        X_te = X_scaled[test_idx]
        y_te = y.iloc[test_idx]

        if use_smote:
            X_tr, y_tr = resample_train(X_tr, y_tr)

        clf = get_base_clf(scale_pos)
        clf.fit(X_tr, y_tr)
        y_proba_raw = clf.predict_proba(X_te)[:, 1]

        from sklearn.model_selection import train_test_split as tts
        X_fit, X_cal, y_fit, y_cal = tts(X_tr, y_tr, test_size=0.25, stratify=y_tr, random_state=RANDOM_STATE + fold_idx)
        if use_smote:
            X_fit, y_fit = resample_train(X_fit, y_fit)
        clf_inner = clone(get_base_clf(scale_pos))
        clf_inner.fit(X_fit, y_fit)
        try:
            calibrated = CalibratedClassifierCV(clf_inner, cv="prefit", method=use_calibration)
            calibrated.fit(X_cal, y_cal)
            y_proba = calibrated.predict_proba(X_te)[:, 1]
        except Exception:
            y_proba = y_proba_raw
        if np.any(np.isnan(y_proba)):
            y_proba = y_proba_raw

        thresh, sens, spec = optimize_threshold(y_te.values, y_proba)
        y_pred = (y_proba >= thresh).astype(int)
        roc = roc_auc_score(y_te, y_proba) if y_te.nunique() > 1 else 0.0
        pr_auc = average_precision_score(y_te, y_proba)
        rec = recall_score(y_te, y_pred, zero_division=0)
        prec = precision_score(y_te, y_pred, zero_division=0)
        f1 = f1_score(y_te, y_pred, zero_division=0)
        brier = brier_score_loss(y_te, y_proba)

        outer_results.append({
            "fold": fold_idx + 1,
            "roc_auc": roc, "pr_auc": pr_auc, "recall": rec, "precision": prec, "f1": f1,
            "brier": brier, "threshold": thresh, "sensitivity": sens, "specificity": spec,
        })
        all_y_true.append(y_te.values)
        all_y_proba.append(y_proba)
        fold_models.append({"var_sel": var_sel, "scaler": scaler, "clf": clf})

    y_true_flat = np.concatenate(all_y_true)
    y_proba_flat = np.concatenate(all_y_proba)

    try:
        from bootstrap_utils import robust_bootstrap_ci
    except ImportError:
        robust_bootstrap_ci = None
    if robust_bootstrap_ci is not None:
        roc_ci_lo, roc_ci_hi, roc_meta = robust_bootstrap_ci(
            y_true_flat, y_proba_flat, roc_auc_score,
            n_boot=N_BOOTSTRAP, random_state=RANDOM_STATE,
            stratified=True, require_both_classes=True, min_valid_samples=50,
            use_tqdm=False, metric_name="ROC-AUC",
        )
        pr_ci_lo, pr_ci_hi, pr_meta = robust_bootstrap_ci(
            y_true_flat, y_proba_flat, average_precision_score,
            n_boot=N_BOOTSTRAP, random_state=RANDOM_STATE + 1,
            stratified=True, require_both_classes=True, min_valid_samples=50,
            use_tqdm=False, metric_name="PR-AUC",
        )
        roc_ci = (float(roc_ci_lo), float(roc_ci_hi))
        pr_ci = (float(pr_ci_lo), float(pr_ci_hi))
    else:
        roc_mean = np.mean([r["roc_auc"] for r in outer_results])
        roc_std = np.std([r["roc_auc"] for r in outer_results])
        pr_mean = np.mean([r["pr_auc"] for r in outer_results])
        pr_std = np.std([r["pr_auc"] for r in outer_results])
        roc_ci = (roc_mean - 1.96 * roc_std, roc_mean + 1.96 * roc_std)
        pr_ci = (pr_mean - 1.96 * pr_std, pr_mean + 1.96 * pr_std)
        roc_meta = pr_meta = {}

    tier_results = risk_tier_analysis(y_true_flat, y_proba_flat)
    try:
        from clinical_triage import recall_at_k, number_needed_to_screen, recall_at_k_curve
        recall_at_20 = recall_at_k(y_true_flat, y_proba_flat, k_fraction=0.20)
        recall_at_k_list = recall_at_k_curve(y_true_flat, y_proba_flat)
        thresh_for_nns = float(np.percentile(y_proba_flat, 80))
        nns_at_20pct = number_needed_to_screen(y_true_flat, y_proba_flat, thresh_for_nns)
    except ImportError:
        recall_at_20 = None
        recall_at_k_list = []
        nns_at_20pct = None

    summary = {
        "n_samples": len(y),
        "n_positives": int(y.sum()),
        "pos_rate_pct": round(float(y.sum() / len(y) * 100), 2),
        "roc_auc_mean": float(np.mean([r["roc_auc"] for r in outer_results])),
        "roc_auc_std": float(np.std([r["roc_auc"] for r in outer_results])),
        "roc_auc_ci": list(roc_ci),
        "roc_auc_bootstrap_meta": roc_meta,
        "pr_auc_mean": float(np.mean([r["pr_auc"] for r in outer_results])),
        "pr_auc_ci": list(pr_ci),
        "pr_auc_bootstrap_meta": pr_meta,
        "recall_mean": float(np.mean([r["recall"] for r in outer_results])),
        "recall_std": float(np.std([r["recall"] for r in outer_results])),
        "recall_at_20pct_intervention": recall_at_20,
        "recall_at_k_curve": recall_at_k_list,
        "nns_at_top20pct": nns_at_20pct,
        "fold_results": outer_results,
        "risk_tiers": tier_results,
        "feature_names_used": sel_names,
    }

    if PLOT_AVAILABLE:
        _plot_calibration_curve(y_true_flat, y_proba_flat, RUN_DIR)
        _plot_risk_tiers(tier_results, RUN_DIR)
        _plot_decision_curve(y_true_flat, y_proba_flat, RUN_DIR)
        if fold_models and hasattr(fold_models[0]["clf"], "feature_importances_"):
            _plot_feature_importance(fold_models, sel_names, RUN_DIR)

    return summary, y_true_flat, y_proba_flat, fold_models


def _plot_calibration_curve(y_true, y_proba, out_dir, n_bins=8, n_boot=80):
    from sklearn.calibration import calibration_curve
    prob_true, prob_pred = calibration_curve(y_true, y_proba, n_bins=n_bins)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(prob_pred, prob_true, "s-", label="Model", color="steelblue")
    rng = np.random.RandomState(RANDOM_STATE)
    n = len(y_true)
    n_main = len(prob_true)
    boot_curves = []
    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        try:
            pt, pp = calibration_curve(y_true[idx], y_proba[idx], n_bins=n_bins)
            if len(pt) == n_main and len(pp) == n_main:
                boot_curves.append((pt, pp))
        except Exception:
            pass
    if boot_curves:
        pt_arr = np.array([c[0] for c in boot_curves])
        lo = np.percentile(pt_arr, 2.5, axis=0)
        hi = np.percentile(pt_arr, 97.5, axis=0)
        ax.fill_between(prob_pred, lo, hi, alpha=0.2, color="steelblue")
    ax.plot([0, 1], [0, 1], "k--", label="Perfect")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title("Prostate: Calibration curve")
    ax.legend()
    fig.savefig(out_dir / "calibration_curve.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_risk_tiers(tier_results, out_dir):
    fig, ax = plt.subplots(figsize=(6, 4))
    bins = [r["bin"] for r in tier_results]
    n_pos = [r["n_pos"] for r in tier_results]
    ax.bar(bins, n_pos, color="coral", alpha=0.8)
    ax.set_xlabel("Risk tier")
    ax.set_ylabel("Number of positives")
    ax.set_title("Prostate: Risk tier analysis")
    fig.savefig(out_dir / "risk_tiers.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_decision_curve(y_true, y_proba, out_dir):
    thresh = np.linspace(0.01, 0.99, 50)
    n = len(y_true)
    nb = []
    for pt in thresh:
        pred = (y_proba >= pt).astype(int)
        tp = ((pred == 1) & (y_true == 1)).sum()
        fp = ((pred == 1) & (y_true == 0)).sum()
        if pt < 1 and pt > 0:
            nb.append(tp / n - (fp / n) * (pt / (1 - pt)))
        else:
            nb.append(0)
    nb = np.array(nb)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(thresh, nb, "b-", label="Model")
    ax.axhline(0, color="gray", linestyle="--", label="Refer none")
    prev = y_true.mean()
    nb_all = prev - (1 - prev) * (thresh / (1 - thresh + 1e-8))
    ax.plot(thresh, np.clip(nb_all, -0.1, 0.5), "k:", label="Refer all")
    ax.set_xlabel("Threshold probability")
    ax.set_ylabel("Net benefit")
    ax.set_title("Prostate: Decision curve")
    ax.legend()
    ax.set_ylim(-0.05, max(0.3, nb.max() + 0.05))
    fig.savefig(out_dir / "decision_curve.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_feature_importance(fold_models, feature_names, out_dir):
    imp = np.mean([m["clf"].feature_importances_ for m in fold_models], axis=0)
    idx = np.argsort(imp)[::-1]
    fig, ax = plt.subplots(figsize=(6, max(4, len(feature_names) * 0.3)))
    ax.barh(range(len(idx)), imp[idx], color="teal", alpha=0.8)
    ax.set_yticks(range(len(idx)))
    ax.set_yticklabels([feature_names[i] for i in idx], fontsize=8)
    ax.set_xlabel("Mean feature importance")
    ax.set_title("Prostate: Feature importance")
    ax.invert_yaxis()
    fig.savefig(out_dir / "feature_importance.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    print("Prostate cancer risk stratification — nested CV, calibration, risk tiers")
    print("=" * 70)
    use_calibration = "isotonic"
    X, y, feature_names = load_prostate_data()
    n_pos = int(y.sum())
    print(f"  Samples: {len(X)}, Positives (M): {n_pos} ({100*n_pos/len(y):.2f}%)")
    print(f"  SMOTE: {IMBLEARN_AVAILABLE}, Calibration: {use_calibration}, Output: {RUN_DIR}")

    summary, y_true, y_proba, _ = run_nested_cv(
        X, y, feature_names,
        use_smote=IMBLEARN_AVAILABLE and n_pos < 45,
        use_calibration=use_calibration,
    )

    with open(RUN_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n  Aggregate (nested CV):")
    print(f"    ROC-AUC:  {summary['roc_auc_mean']:.4f} ± {summary['roc_auc_std']:.4f}  (95% CI: {summary['roc_auc_ci']})")
    print(f"    PR-AUC:   {summary['pr_auc_mean']:.4f}  (95% CI: {summary['pr_auc_ci']})")
    print(f"    Recall:   {summary['recall_mean']:.4f} ± {summary['recall_std']:.4f}")
    print(f"    Recall@20%: {summary.get('recall_at_20pct_intervention')}")
    print("  Risk tiers:", summary["risk_tiers"])
    print(f"\n  Results saved to {RUN_DIR}")


if __name__ == "__main__":
    main()
