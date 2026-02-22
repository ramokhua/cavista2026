"""
GeneShield — Enhanced Training Pipeline for Cervical & Prostate Cancer Models
==============================================================================
- Cervical: SMOTE/class weighting, stratified 5-fold CV, recall-optimized,
  ensemble (Random Forest + XGBoost + LightGBM) with voting classifier.
- Prostate: Leave-one-out CV, Logistic Regression L2, SVM linear, feature
  selection, bagging, confidence intervals (small dataset).
- Evaluation: ROC-AUC, Precision-Recall curves, calibration plots,
  feature importance, 20% holdout, DummyClassifier baseline, McNemar's test.
- Saves versioned models to models/ and generates evaluation report with plots.
"""

import os
import sys
import urllib.request
import zipfile
import shutil
import warnings
from datetime import datetime
from collections import defaultdict

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import (
    RandomForestClassifier,
    VotingClassifier,
    BaggingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    LeaveOneOut,
    cross_val_score,
    cross_val_predict,
)
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
    average_precision_score,
)
from sklearn.calibration import calibration_curve

warnings.filterwarnings("ignore")

# Optional imports for ensemble and resampling
try:
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as ImbPipeline
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOT_AVAILABLE = True
except ImportError:
    PLOT_AVAILABLE = False

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# Version for this run (used in filenames)
RUN_VERSION = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_DIR = os.path.join(REPORTS_DIR, RUN_VERSION)
os.makedirs(REPORT_DIR, exist_ok=True)

# ============== Data config (same as train_models.py) ==============
CERVICAL_FEATURE_MAP = {
    "Age": "Age",
    "Number of sexual partners": "Number of sexual partners",
    "First sexual intercourse": "First sexual intercourse",
    "First sexual intercourse (age)": "First sexual intercourse",
    "Num of pregnancies": "Num of pregnancies",
    "Smokes": "Smokes",
    "Smokes (years)": "Smokes (years)",
    "Hormonal Contraceptives": "Hormonal Contraceptives",
    "Hormonal Contraceptives (years)": "Hormonal Contraceptives (years)",
    "IUD": "IUD",
    "IUD (years)": "IUD (years)",
    "STDs (number)": "STDs (number)",
    "STDs:HPV": "STDs:HPV",
    "STDs:HIV": "STDs:HIV",
    "Dx:Cancer": "Dx:Cancer",
    "Dx:CIN": "Dx:CIN",
    "Dx:HPV": "Dx:HPV",
    "Hinselmann": "Hinselmann",
    "Schiller": "Schiller",
    "Citology": "Citology",
    "Citology ": "Citology",
}
CERVICAL_STANDARD_FEATURES = [
    "Age", "Number of sexual partners", "First sexual intercourse",
    "Num of pregnancies", "Smokes", "Smokes (years)",
    "Hormonal Contraceptives", "Hormonal Contraceptives (years)",
    "IUD", "IUD (years)", "STDs (number)", "STDs:HPV", "STDs:HIV",
    "Dx:Cancer", "Dx:CIN", "Dx:HPV", "Hinselmann", "Schiller", "Citology",
]
CERVICAL_TARGET = "Biopsy"
PROSTATE_FEATURES = [
    "radius", "texture", "perimeter", "area",
    "smoothness", "compactness", "symmetry", "fractal_dimension",
]
PROSTATE_TARGET_COL = "diagnosis_result"
PROSTATE_CSV_URL = "https://raw.githubusercontent.com/bikramb98/prostate-cancer-prediction/master/Prostate_Cancer.csv"
CERVICAL_ZIP_URL = "https://archive.ics.uci.edu/static/public/383/cervical+cancer+risk+factors.zip"


def download_file(url, dest_path):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GeneShield-Train/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(dest_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"  Download error: {e}")
        return False


def ensure_prostate_data():
    path = os.path.join(DATA_DIR, "Prostate_Cancer.csv")
    if os.path.exists(path):
        print("[Prostate] Using existing data/Prostate_Cancer.csv")
        return path
    print("[Prostate] Downloading Prostate_Cancer.csv...")
    if download_file(PROSTATE_CSV_URL, path):
        print("[Prostate] Download OK.")
        return path
    return None


def ensure_cervical_data():
    for name in ["risk_factors_cervical_cancer.csv", "cervical-cancer_csv.csv"]:
        path = os.path.join(DATA_DIR, name)
        if os.path.exists(path):
            print(f"[Cervical] Using {name} with enhanced preprocessing")
            return path
    zip_path = os.path.join(DATA_DIR, "cervical_uci.zip")
    print("[Cervical] Attempting download from UCI...")
    if download_file(CERVICAL_ZIP_URL, zip_path):
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                for info in z.namelist():
                    if info.endswith(".csv"):
                        z.extract(info, DATA_DIR)
                        base = os.path.basename(info)
                        extracted = os.path.join(DATA_DIR, info)
                        target = os.path.join(DATA_DIR, base)
                        if os.path.exists(extracted):
                            if extracted != target:
                                shutil.move(extracted, target)
                            return target
        except Exception as e:
            print(f"  Zip extract error: {e}")
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except OSError:
                    pass
    print("[Cervical] Place risk_factors_cervical_cancer.csv in data/")
    return None


def normalize_cervical_columns(df):
    standard_to_variants = {}
    for variant, standard in CERVICAL_FEATURE_MAP.items():
        standard_to_variants.setdefault(standard, []).append(variant)
    rename = {}
    for col in df.columns:
        col_stripped = col.strip()
        for standard, variants in standard_to_variants.items():
            if col_stripped in variants or col_stripped == standard:
                rename[col] = standard
                break
    return df.rename(columns=rename)


def load_cervical_df(csv_path):
    df = pd.read_csv(csv_path)
    df = normalize_cervical_columns(df)
    df = df.replace("?", np.nan)
    if CERVICAL_TARGET not in df.columns:
        raise ValueError(f"Target '{CERVICAL_TARGET}' not found")
    for col in CERVICAL_STANDARD_FEATURES + [CERVICAL_TARGET]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    y = df[CERVICAL_TARGET].copy()
    valid = y.notna()
    df = df.loc[valid]
    y = y[valid].astype(int)
    available = [f for f in CERVICAL_STANDARD_FEATURES if f in df.columns]
    X = df[available].copy()
    return X, y, available


def load_prostate_df(csv_path):
    df = pd.read_csv(csv_path)
    if PROSTATE_TARGET_COL not in df.columns:
        raise ValueError(f"Target '{PROSTATE_TARGET_COL}' not found")
    df[PROSTATE_TARGET_COL] = df[PROSTATE_TARGET_COL].map({"M": 1, "B": 0})
    df = df.dropna(subset=[PROSTATE_TARGET_COL])
    y = df[PROSTATE_TARGET_COL].astype(int)
    available = [f for f in PROSTATE_FEATURES if f in df.columns]
    X = df[available].copy()
    return X, y, available


def _bootstrap_ci(y_true, y_pred_proba, metric_fn, n_bootstrap=500, seed=42):
    """Bootstrap 95% CI for a metric that uses y_pred_proba (e.g. roc_auc)."""
    rng = np.random.RandomState(seed)
    n = len(y_true)
    scores = []
    for _ in range(n_bootstrap):
        idx = rng.randint(0, n, n)
        try:
            s = metric_fn(y_true[idx], y_pred_proba[idx])
            scores.append(s)
        except Exception:
            pass
    scores = np.array(scores)
    return np.percentile(scores, 2.5), np.percentile(scores, 97.5)


def _mcnemar_table(y_true, y_pred_a, y_pred_b):
    """Contingency table for McNemar: b00=both wrong, b11=both right, b01=a wrong b right, b10=a right b wrong."""
    b00 = np.sum((y_pred_a != y_true) & (y_pred_b != y_true))
    b11 = np.sum((y_pred_a == y_true) & (y_pred_b == y_true))
    b01 = np.sum((y_pred_a != y_true) & (y_pred_b == y_true))
    b10 = np.sum((y_pred_a == y_true) & (y_pred_b != y_true))
    return np.array([[b00, b01], [b10, b11]])


def _save_plot(fig, name):
    path = os.path.join(REPORT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


# ==================== CERVICAL: Enhanced pipeline ====================

def train_cervical_enhanced():
    csv_path = ensure_cervical_data()
    if not csv_path:
        return None

    X, y, feature_names = load_cervical_df(csv_path)
    n_pos = int(y.sum())
    n_neg = int((y == 0).sum())
    print(f"  Class balance: {n_neg} negative, {n_pos} positive (imbalanced)")

    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    # 20% stratified holdout (same class distribution)
    X_train, X_holdout, y_train, y_holdout = train_test_split(
        X_scaled, y, test_size=0.20, random_state=42, stratify=y
    )

    # SMOTE only on training (with safe k_neighbors for small positive class)
    if IMBLEARN_AVAILABLE and n_pos >= 3:
        k = min(3, n_pos - 1) if n_pos <= 5 else 5
        try:
            smote = SMOTE(random_state=42, k_neighbors=k)
            X_train, y_train = smote.fit_resample(X_train, y_train)
            print(f"  Applied SMOTE (k_neighbors={k}); resampled train size: {len(y_train)}")
        except Exception as e:
            print(f"  SMOTE skipped: {e}; using class_weight instead")
    # If no SMOTE, we use class_weight in the estimators

    # Stratified 5-fold CV, optimize for recall
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # Ensemble: RF + XGBoost + LightGBM with class_weight / scale_pos_weight for recall
    estimators = []
    rf = RandomForestClassifier(n_estimators=150, max_depth=10, class_weight="balanced", random_state=42)
    estimators.append(("rf", rf))

    if XGB_AVAILABLE:
        scale_pos = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
        xgb_clf = xgb.XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.05,
            scale_pos_weight=scale_pos, use_label_encoder=False, eval_metric="logloss", random_state=42
        )
        estimators.append(("xgb", xgb_clf))

    if LGB_AVAILABLE:
        lgb_clf = lgb.LGBMClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.05,
            class_weight="balanced", verbose=-1, random_state=42
        )
        estimators.append(("lgb", lgb_clf))

    if len(estimators) < 2:
        model = rf
        print("  Using Random Forest only (install xgboost/lightgbm for full ensemble)")
    else:
        model = VotingClassifier(estimators=estimators, voting="soft")

    # Cross-val recall
    recall_cv = cross_val_score(model, X_train, y_train, cv=skf, scoring="recall", n_jobs=-1)
    print(f"  5-fold CV recall: {recall_cv.mean():.4f} (+/- {recall_cv.std() * 2:.4f})")

    model.fit(X_train, y_train)
    y_holdout_pred = model.predict(X_holdout)
    y_holdout_proba = model.predict_proba(X_holdout)[:, 1]

    # Baseline
    dummy = DummyClassifier(strategy="stratified", random_state=42)
    dummy.fit(X_train, y_train)
    y_dummy = dummy.predict(X_holdout)

    # Metrics
    acc = accuracy_score(y_holdout, y_holdout_pred)
    prec = precision_score(y_holdout, y_holdout_pred, zero_division=0)
    rec = recall_score(y_holdout, y_holdout_pred, zero_division=0)
    f1 = f1_score(y_holdout, y_holdout_pred, zero_division=0)
    try:
        roc_auc = roc_auc_score(y_holdout, y_holdout_proba)
    except Exception:
        roc_auc = 0.0
    avg_prec = average_precision_score(y_holdout, y_holdout_proba)

    acc_dummy = accuracy_score(y_holdout, y_dummy)
    rec_dummy = recall_score(y_holdout, y_dummy, zero_division=0)

    # McNemar (model vs dummy)
    mcnemar_p = None
    if SCIPY_AVAILABLE:
        tbl = _mcnemar_table(y_holdout.values, y_holdout_pred, y_dummy)
        b01, b10 = tbl[0, 1], tbl[1, 0]
        if b01 + b10 > 0:
            mcnemar_stat = (np.abs(b01 - b10) - 1) ** 2 / (b01 + b10)
            mcnemar_p = 1 - stats.chi2.cdf(mcnemar_stat, 1)

    results = {
        "model": model,
        "scaler": scaler,
        "imputer": imputer,
        "feature_names": feature_names,
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "roc_auc": roc_auc,
        "average_precision": avg_prec,
        "recall_cv_mean": recall_cv.mean(),
        "recall_cv_std": recall_cv.std(),
        "baseline_accuracy": acc_dummy,
        "baseline_recall": rec_dummy,
        "mcnemar_p": mcnemar_p,
        "y_holdout": y_holdout,
        "y_pred": y_holdout_pred,
        "y_proba": y_holdout_proba,
        "confusion_matrix": confusion_matrix(y_holdout, y_holdout_pred),
    }

    # Feature importance (from RF if ensemble)
    if hasattr(model, "named_estimators_") and "rf" in model.named_estimators_:
        rf_est = model.named_estimators_["rf"]
        results["feature_importance"] = rf_est.feature_importances_
    elif hasattr(model, "feature_importances_"):
        results["feature_importance"] = model.feature_importances_
    else:
        results["feature_importance"] = np.ones(len(feature_names)) / len(feature_names)

    # Plots
    if PLOT_AVAILABLE:
        # ROC
        fpr, tpr, _ = roc_curve(y_holdout, y_holdout_proba)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(fpr, tpr, label=f"Model (AUC={roc_auc:.3f})")
        ax.plot([0, 1], [0, 1], "k--")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title("Cervical: ROC Curve")
        ax.legend()
        ax.grid(True, alpha=0.3)
        _save_plot(fig, "cervical_roc.png")

        # Precision-Recall
        prec_curve, rec_curve, _ = precision_recall_curve(y_holdout, y_holdout_proba)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(rec_curve, prec_curve, label=f"Model (AP={avg_prec:.3f})")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title("Cervical: Precision-Recall Curve")
        ax.legend()
        ax.grid(True, alpha=0.3)
        _save_plot(fig, "cervical_pr_curve.png")

        # Calibration
        prob_true, prob_pred = calibration_curve(y_holdout, y_holdout_proba, n_bins=10)
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.plot(prob_pred, prob_true, "s-", label="Model")
        ax.plot([0, 1], [0, 1], "k--", label="Perfect")
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Fraction of positives")
        ax.set_title("Cervical: Calibration")
        ax.legend()
        _save_plot(fig, "cervical_calibration.png")

        # Feature importance
        imp = results["feature_importance"]
        idx = np.argsort(imp)[::-1]
        fig, ax = plt.subplots(figsize=(8, max(4, len(feature_names) * 0.25)))
        ax.barh(range(len(idx)), imp[idx], color="steelblue", alpha=0.8)
        ax.set_yticks(range(len(idx)))
        ax.set_yticklabels([feature_names[i] for i in idx], fontsize=8)
        ax.set_xlabel("Importance")
        ax.set_title("Cervical: Feature Importance")
        ax.invert_yaxis()
        _save_plot(fig, "cervical_feature_importance.png")

    return results


# ==================== PROSTATE: Small-sample pipeline ====================

def train_prostate_enhanced():
    csv_path = ensure_prostate_data()
    if not csv_path:
        return None

    X, y, feature_names = load_prostate_df(csv_path)
    n = len(X)
    print(f"  Dataset size: {n} (small — using LOOCV, simple models, feature selection)")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Feature selection: top k (reduce dimensionality)
    k_features = min(5, n // 5, len(feature_names))
    k_features = max(2, k_features)
    selector = SelectKBest(score_func=f_classif, k=k_features)
    X_selected = selector.fit_transform(X_scaled, y)
    selected_idx = selector.get_support(indices=True)
    selected_features = [feature_names[i] for i in selected_idx]
    print(f"  Selected top {k_features} features: {selected_features}")

    # 20% holdout for final metrics (stratified)
    X_tr, X_holdout, y_tr, y_holdout = train_test_split(
        X_selected, y, test_size=0.20, random_state=42, stratify=y
    )

    # Simple models: Logistic Regression L2 + SVM linear, then bagging
    lr = LogisticRegression(penalty="l2", C=1.0, max_iter=1000, random_state=42)
    svm = SVC(kernel="linear", C=0.5, probability=True, random_state=42)
    # Bagging with LR base for stability
    bagged_lr = BaggingClassifier(estimator=lr, n_estimators=20, random_state=42)
    bagged_lr.fit(X_tr, y_tr)
    y_holdout_pred = bagged_lr.predict(X_holdout)
    y_holdout_proba = bagged_lr.predict_proba(X_holdout)[:, 1]

    # Leave-one-out cross-validation on full dataset for stable metrics
    loo = LeaveOneOut()
    y_loo_pred = cross_val_predict(bagged_lr, X_selected, y, cv=loo, n_jobs=-1)
    y_loo_proba = cross_val_predict(bagged_lr, X_selected, y, cv=loo, method="predict_proba", n_jobs=-1)[:, 1]

    acc_loo = accuracy_score(y, y_loo_pred)
    rec_loo = recall_score(y, y_loo_pred, zero_division=0)
    prec_loo = precision_score(y, y_loo_pred, zero_division=0)
    f1_loo = f1_score(y, y_loo_pred, zero_division=0)
    try:
        roc_auc_loo = roc_auc_score(y, y_loo_proba)
    except Exception:
        roc_auc_loo = 0.0

    # Bootstrap 95% CI for ROC-AUC (small sample)
    roc_ci_lo, roc_ci_hi = _bootstrap_ci(y, y_loo_proba, roc_auc_score)
    acc_ci_lo, acc_ci_hi = _bootstrap_ci(
        y, y_loo_proba,
        lambda yt, yp: accuracy_score(yt, (np.array(yp) >= 0.5).astype(int))
    )

    # Baseline
    dummy = DummyClassifier(strategy="stratified", random_state=42)
    dummy.fit(X_tr, y_tr)
    y_dummy = dummy.predict(X_holdout)
    acc_dummy = accuracy_score(y_holdout, y_dummy)

    # McNemar
    mcnemar_p = None
    if SCIPY_AVAILABLE and len(y_holdout) >= 10:
        tbl = _mcnemar_table(y_holdout.values, y_holdout_pred, y_dummy)
        b01, b10 = tbl[0, 1], tbl[1, 0]
        if b01 + b10 > 0:
            mcnemar_stat = (np.abs(b01 - b10) - 1) ** 2 / (b01 + b10)
            mcnemar_p = 1 - stats.chi2.cdf(mcnemar_stat, 1)

    # Final model for saving: refit on full data with selector + bagged LR
    # Pipeline: scale -> select -> classify
    from sklearn.pipeline import Pipeline
    pipe = Pipeline([
        ("scaler", scaler),
        ("selector", selector),
        ("classifier", bagged_lr),
    ])
    # Refit selector and classifier on full data
    X_full = scaler.transform(X)
    X_full_sel = selector.transform(X_full)
    bagged_lr.fit(X_full_sel, y)
    pipe.steps[-1] = ("classifier", bagged_lr)

    results = {
        "model": pipe,
        "scaler": scaler,
        "selector": selector,
        "feature_names": feature_names,
        "selected_features": selected_features,
        "accuracy_holdout": accuracy_score(y_holdout, y_holdout_pred),
        "roc_auc_loo": roc_auc_loo,
        "roc_auc_ci": (roc_ci_lo, roc_ci_hi),
        "accuracy_loo": acc_loo,
        "accuracy_ci": (acc_ci_lo, acc_ci_hi),
        "recall_loo": rec_loo,
        "precision_loo": prec_loo,
        "f1_loo": f1_loo,
        "baseline_accuracy": acc_dummy,
        "mcnemar_p": mcnemar_p,
        "y_holdout": y_holdout,
        "y_pred": y_holdout_pred,
        "y_proba": y_holdout_proba,
        "confusion_matrix": confusion_matrix(y_holdout, y_holdout_pred),
        "feature_importance": selector.scores_[selected_idx],
    }

    if PLOT_AVAILABLE:
        fpr, tpr, _ = roc_curve(y_holdout, y_holdout_proba)
        roc_auc_h = roc_auc_score(y_holdout, y_holdout_proba) if y_holdout.nunique() > 1 else 0.0
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(fpr, tpr, label=f"Model (AUC={roc_auc_h:.3f})")
        ax.plot([0, 1], [0, 1], "k--")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title("Prostate: ROC Curve (holdout)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        _save_plot(fig, "prostate_roc.png")

        prec_curve, rec_curve, _ = precision_recall_curve(y_holdout, y_holdout_proba)
        fig, ax = plt.subplots(figsize=(6, 5))
        ap = average_precision_score(y_holdout, y_holdout_proba)
        ax.plot(rec_curve, prec_curve, label=f"Model (AP={ap:.3f})")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title("Prostate: Precision-Recall Curve")
        ax.legend()
        ax.grid(True, alpha=0.3)
        _save_plot(fig, "prostate_pr_curve.png")

        prob_true, prob_pred = calibration_curve(y_holdout, y_holdout_proba, n_bins=min(10, len(y_holdout) // 2))
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.plot(prob_pred, prob_true, "s-", label="Model")
        ax.plot([0, 1], [0, 1], "k--", label="Perfect")
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Fraction of positives")
        ax.set_title("Prostate: Calibration")
        ax.legend()
        _save_plot(fig, "prostate_calibration.png")

        fig, ax = plt.subplots(figsize=(6, max(3, len(selected_features) * 0.4)))
        scores = selector.scores_[selected_idx]
        ax.barh(selected_features, scores, color="coral", alpha=0.8)
        ax.set_xlabel("F-score")
        ax.set_title("Prostate: Selected Feature Scores")
        ax.invert_yaxis()
        _save_plot(fig, "prostate_feature_scores.png")

    return results


# ==================== Save models (versioned + default) ====================

def save_cervical_artifacts(results):
    if not results:
        return
    v = RUN_VERSION
    joblib.dump(results["model"], os.path.join(MODELS_DIR, f"cervical_model_v_{v}.pkl"))
    joblib.dump(results["scaler"], os.path.join(MODELS_DIR, f"cervical_scaler_v_{v}.pkl"))
    joblib.dump(results["imputer"], os.path.join(MODELS_DIR, f"cervical_imputer_v_{v}.pkl"))
    joblib.dump(results["feature_names"], os.path.join(MODELS_DIR, f"cervical_features_v_{v}.pkl"))
    # Default names for ml_engine
    joblib.dump(results["model"], os.path.join(MODELS_DIR, "cervical_model.pkl"))
    joblib.dump(results["scaler"], os.path.join(MODELS_DIR, "cervical_scaler.pkl"))
    joblib.dump(results["imputer"], os.path.join(MODELS_DIR, "cervical_imputer.pkl"))
    joblib.dump(results["feature_names"], os.path.join(MODELS_DIR, "cervical_features.pkl"))
    print(f"[Cervical] Saved versioned + default models to models/")


def save_prostate_artifacts(results):
    if not results:
        return
    v = RUN_VERSION
    # Prostate model is a pipeline (scaler + selector + classifier)
    joblib.dump(results["model"], os.path.join(MODELS_DIR, f"prostate_model_v_{v}.pkl"))
    joblib.dump(results["scaler"], os.path.join(MODELS_DIR, f"prostate_scaler_v_{v}.pkl"))
    joblib.dump(results["selector"], os.path.join(MODELS_DIR, f"prostate_selector_v_{v}.pkl"))
    joblib.dump(results["feature_names"], os.path.join(MODELS_DIR, f"prostate_features_v_{v}.pkl"))
    joblib.dump(results["selected_features"], os.path.join(MODELS_DIR, f"prostate_selected_features_v_{v}.pkl"))
    joblib.dump(results["model"], os.path.join(MODELS_DIR, "prostate_model.pkl"))
    joblib.dump(results["scaler"], os.path.join(MODELS_DIR, "prostate_scaler.pkl"))
    joblib.dump(results["selector"], os.path.join(MODELS_DIR, "prostate_selector.pkl"))
    joblib.dump(results["feature_names"], os.path.join(MODELS_DIR, "prostate_features.pkl"))
    joblib.dump(results["selected_features"], os.path.join(MODELS_DIR, "prostate_selected_features.pkl"))
    print(f"[Prostate] Saved versioned + default models to models/")


# ==================== Report ====================

def write_report(cervical_results, prostate_results):
    path = os.path.join(REPORT_DIR, "evaluation_report.md")
    lines = [
        "# GeneShield — Enhanced Training Evaluation Report",
        f"**Run version:** {RUN_VERSION}",
        "",
        "## 1. Cervical Cancer Model",
        "",
    ]
    if cervical_results:
        r = cervical_results
        lines.extend([
            "- **Strategy:** SMOTE/class weighting, stratified 5-fold CV, recall-optimized ensemble (RF + XGBoost + LightGBM).",
            f"- **5-fold CV Recall:** {r['recall_cv_mean']:.4f} (± {r['recall_cv_std'] * 2:.4f})",
            f"- **Holdout (20%) Accuracy:** {r['accuracy']:.4f}",
            f"- **Holdout Precision / Recall / F1:** {r['precision']:.4f} / {r['recall']:.4f} / {r['f1']:.4f}",
            f"- **ROC-AUC:** {r['roc_auc']:.4f}",
            f"- **Average Precision (PR):** {r['average_precision']:.4f}",
            f"- **Baseline (Dummy) Accuracy / Recall:** {r['baseline_accuracy']:.4f} / {r['baseline_recall']:.4f}",
            f"- **McNemar's test (vs baseline) p-value:** {r['mcnemar_p'] if r['mcnemar_p'] is not None else 'N/A'}",
            "",
            "### Confusion Matrix (holdout)",
            "```",
            str(r["confusion_matrix"]),
            "```",
            "",
            "### Plots",
            "- ROC: `cervical_roc.png`",
            "- Precision-Recall: `cervical_pr_curve.png`",
            "- Calibration: `cervical_calibration.png`",
            "- Feature importance: `cervical_feature_importance.png`",
            "",
        ])
    else:
        lines.append("Cervical model not trained (no data).\n")

    lines.extend(["## 2. Prostate Cancer Model", ""])
    if prostate_results:
        r = prostate_results
        lines.extend([
            "- **Strategy:** Leave-one-out CV, feature selection (SelectKBest), Logistic Regression L2 + Bagging, small-sample CIs.",
            f"- **Selected features:** {r['selected_features']}",
            f"- **LOOCV Accuracy:** {r['accuracy_loo']:.4f} (95% CI: {r['accuracy_ci'][0]:.4f}–{r['accuracy_ci'][1]:.4f})",
            f"- **LOOCV Recall / Precision / F1:** {r['recall_loo']:.4f} / {r['precision_loo']:.4f} / {r['f1_loo']:.4f}",
            f"- **ROC-AUC (LOO):** {r['roc_auc_loo']:.4f} (95% CI: {r['roc_auc_ci'][0]:.4f}–{r['roc_auc_ci'][1]:.4f})",
            f"- **Holdout Accuracy:** {r['accuracy_holdout']:.4f}",
            f"- **Baseline (Dummy) Accuracy:** {r['baseline_accuracy']:.4f}",
            f"- **McNemar's test (vs baseline) p-value:** {r['mcnemar_p'] if r['mcnemar_p'] is not None else 'N/A'}",
            "",
            "### Confusion Matrix (holdout)",
            "```",
            str(r["confusion_matrix"]),
            "```",
            "",
            "### Plots",
            "- ROC: `prostate_roc.png`",
            "- Precision-Recall: `prostate_pr_curve.png`",
            "- Calibration: `prostate_calibration.png`",
            "- Feature scores: `prostate_feature_scores.png`",
            "",
        ])
    else:
        lines.append("Prostate model not trained (no data).\n")

    lines.append(f"\n---\n*Report and figures saved in `reports/{RUN_VERSION}/`*")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[Report] Written to {path}")


# ==================== INFERENCE (for Flask app) ====================

def predict_cervical(user_data):
    """Predict cervical cancer probability using saved model (for API)."""
    model_path = os.path.join(MODELS_DIR, "cervical_model.pkl")
    if not os.path.exists(model_path):
        return None
    model = joblib.load(model_path)
    scaler = joblib.load(os.path.join(MODELS_DIR, "cervical_scaler.pkl"))
    imputer = joblib.load(os.path.join(MODELS_DIR, "cervical_imputer.pkl"))
    features = joblib.load(os.path.join(MODELS_DIR, "cervical_features.pkl"))
    row = {
        "Age": user_data.get("age", np.nan),
        "Number of sexual partners": user_data.get("sexual_partners", np.nan),
        "First sexual intercourse": user_data.get("first_intercourse", np.nan),
        "Num of pregnancies": user_data.get("pregnancies", np.nan),
        "Smokes": 1 if str(user_data.get("smoke", "no")).lower() in ("yes", "occasionally") else 0,
        "Smokes (years)": user_data.get("smoke_years", 0),
        "Hormonal Contraceptives": user_data.get("hormonal_contraceptives", np.nan),
        "Hormonal Contraceptives (years)": user_data.get("hc_years", np.nan),
        "IUD": user_data.get("iud", np.nan),
        "IUD (years)": user_data.get("iud_years", np.nan),
        "STDs (number)": user_data.get("stds_number", 0),
        "STDs:HPV": user_data.get("stds_hpv", 0),
        "STDs:HIV": user_data.get("stds_hiv", 0),
        "Dx:Cancer": user_data.get("dx_cancer", 0),
        "Dx:CIN": user_data.get("dx_cin", 0),
        "Dx:HPV": user_data.get("dx_hpv", 0),
        "Hinselmann": user_data.get("hinselmann", np.nan),
        "Schiller": user_data.get("schiller", np.nan),
        "Citology": user_data.get("citology", np.nan),
    }
    row_df = pd.DataFrame([row])
    for f in features:
        if f not in row_df.columns:
            row_df[f] = np.nan
    X = row_df[features]
    X_imputed = imputer.transform(X)
    X_scaled = scaler.transform(X_imputed)
    prob = model.predict_proba(X_scaled)[0][1]
    return round(float(prob) * 100, 1)


def predict_prostate(user_data):
    """Predict prostate cancer probability using saved model (for API). Supports pipeline (scaler+selector+classifier) or legacy classifier."""
    row = {
        "radius": user_data.get("radius", np.nan),
        "texture": user_data.get("texture", np.nan),
        "perimeter": user_data.get("perimeter", np.nan),
        "area": user_data.get("area", np.nan),
        "smoothness": user_data.get("smoothness", np.nan),
        "compactness": user_data.get("compactness", np.nan),
        "symmetry": user_data.get("symmetry", np.nan),
        "fractal_dimension": user_data.get("fractal_dimension", np.nan),
    }
    if all(pd.isna(v) for v in row.values()):
        return None
    model_path = os.path.join(MODELS_DIR, "prostate_model.pkl")
    if not os.path.exists(model_path):
        return None
    model = joblib.load(model_path)
    features_path = os.path.join(MODELS_DIR, "prostate_features.pkl")
    features = joblib.load(features_path) if os.path.exists(features_path) else PROSTATE_FEATURES
    row_df = pd.DataFrame([row])
    for f in features:
        if f not in row_df.columns:
            row_df[f] = np.nan
    X = row_df[features].fillna(pd.DataFrame([row]).median())
    if hasattr(model, "steps"):
        prob = model.predict_proba(X)[0][1]
    else:
        scaler = joblib.load(os.path.join(MODELS_DIR, "prostate_scaler.pkl"))
        X_scaled = scaler.transform(X)
        prob = model.predict_proba(X_scaled)[0][1]
    return round(float(prob) * 100, 1)


# ==================== HEREDITARY RISK (for Flask app) ====================

BASE_RISKS = {
    "breast_cancer": 0.12,
    "cervical_cancer": 0.007,
    "prostate_cancer": 0.12,
    "colorectal_cancer": 0.04,
    "lung_cancer": 0.06,
    "ovarian_cancer": 0.012,
    "skin_cancer": 0.02,
    "stomach_cancer": 0.01,
}
FAMILY_MULTIPLIERS = {
    "first_degree": {"breast_cancer": 2.0, "cervical_cancer": 1.6, "colorectal_cancer": 2.2, "prostate_cancer": 2.5, "lung_cancer": 1.5, "ovarian_cancer": 1.8, "skin_cancer": 1.7, "stomach_cancer": 1.5},
    "second_degree": {"breast_cancer": 1.5, "cervical_cancer": 1.3, "colorectal_cancer": 1.6, "prostate_cancer": 1.7, "lung_cancer": 1.25, "ovarian_cancer": 1.4, "skin_cancer": 1.35, "stomach_cancer": 1.25},
    "both_parents": {"breast_cancer": 4.0, "cervical_cancer": 2.5, "colorectal_cancer": 4.0, "prostate_cancer": 5.0, "lung_cancer": 2.5, "ovarian_cancer": 3.0, "skin_cancer": 2.5, "stomach_cancer": 2.5},
}
AGE_MODIFIERS = {(0, 29): 0.5, (30, 44): 1.0, (45, 59): 1.8, (60, 120): 2.5}
FEMALE_ONLY = {"cervical_cancer", "ovarian_cancer"}
MALE_ONLY = {"prostate_cancer"}
FEMALE_HIGHER = {"breast_cancer"}


def _get_age_modifier(age):
    for (lo, hi), mod in AGE_MODIFIERS.items():
        if lo <= age <= hi:
            return mod
    return 1.0


def _get_lifestyle_modifier(profile):
    modifier, factors, bmi = 1.0, [], 0
    smoke = (profile.get("smoke") or "").lower()
    if smoke in ("yes", "current", "regularly"):
        modifier *= 1.40
        factors.append("Smoking (+40% risk)")
    elif smoke == "occasionally":
        modifier *= 1.15
    weight = float(profile.get("weight") or 0)
    height = float(profile.get("height") or 0)
    if weight > 0 and height > 0:
        bmi = weight / ((height / 100) ** 2)
        if bmi > 30:
            modifier *= 1.25
        elif bmi > 25:
            modifier *= 1.10
    exercise = (profile.get("exercise") or "").lower()
    if exercise in ("never", "none", "sedentary"):
        modifier *= 1.25
    alcohol = (profile.get("alcohol") or "").lower()
    if alcohol in ("yes", "regularly", "heavy", "daily"):
        modifier *= 1.20
    diet = (profile.get("diet") or "").lower()
    if diet in ("excellent", "very healthy", "good"):
        modifier *= 0.88
    return modifier, factors, bmi


def _get_family_multiplier(cancer_type, father_history, mother_history, grand_history):
    father_has = cancer_type in (father_history or [])
    mother_has = cancer_type in (mother_history or [])
    grand_has = cancer_type in (grand_history or [])
    if father_has and mother_has:
        return FAMILY_MULTIPLIERS["both_parents"].get(cancer_type, 3.0), "both parents"
    elif father_has or mother_has:
        return FAMILY_MULTIPLIERS["first_degree"].get(cancer_type, 1.5), "one parent"
    elif grand_has:
        return FAMILY_MULTIPLIERS["second_degree"].get(cancer_type, 1.3), "grandparent"
    return 1.0, "none"


def calculate_hereditary_risk(user_profile):
    import json
    gender = (user_profile.get("gender") or "").lower()
    dob = user_profile.get("dob")
    age = 35
    if dob:
        try:
            from datetime import datetime
            birth = datetime.strptime(str(dob), "%Y-%m-%d")
            age = (datetime.now() - birth).days // 365
        except (ValueError, TypeError):
            pass
    father_h = user_profile.get("fatherHistory") or user_profile.get("father_history") or []
    mother_h = user_profile.get("motherHistory") or user_profile.get("mother_history") or []
    grand_h = user_profile.get("grandHistory") or user_profile.get("grand_history") or []
    for var, val in [("father_h", father_h), ("mother_h", mother_h), ("grand_h", grand_h)]:
        if isinstance(val, str):
            try:
                if var == "father_h":
                    father_h = json.loads(val)
                elif var == "mother_h":
                    mother_h = json.loads(val)
                else:
                    grand_h = json.loads(val)
            except Exception:
                pass
    age_mod = _get_age_modifier(age)
    lifestyle_mod, lifestyle_factors, bmi = _get_lifestyle_modifier(user_profile)
    results = {}
    family_analysis = {}
    for cancer_type, base_risk in BASE_RISKS.items():
        if cancer_type in FEMALE_ONLY and gender == "male":
            continue
        if cancer_type in MALE_ONLY and gender == "female":
            continue
        if cancer_type in FEMALE_HIGHER and gender == "male":
            base_risk *= 0.01
        fam_mult, fam_source = _get_family_multiplier(cancer_type, father_h, mother_h, grand_h)
        combined_mult = fam_mult * lifestyle_mod * age_mod
        risk = 1 - (1 - base_risk) ** combined_mult
        risk_pct = round(min(max(risk * 100, 3), 95), 1)
        results[cancer_type] = risk_pct
        family_analysis[cancer_type] = {"risk_percent": risk_pct, "base_risk": round(base_risk * 100, 2), "family_multiplier": round(fam_mult, 2), "family_source": fam_source}
    return results, {"family_analysis": family_analysis, "lifestyle_factors": lifestyle_factors, "age": age, "gender": gender}


def calculate_all_risks(user_profile):
    hereditary_risks, details = calculate_hereditary_risk(user_profile)
    gender = (user_profile.get("gender") or "").lower()
    age = details.get("age", 35)
    if gender != "male":
        ml_cervical = predict_cervical({"age": age, "smoke": user_profile.get("smoke", "no"), **user_profile})
        if ml_cervical is not None:
            hereditary_val = hereditary_risks.get("cervical_cancer", 5)
            blended = round(0.6 * ml_cervical + 0.4 * hereditary_val, 1)
            hereditary_risks["cervical_cancer"] = min(max(blended, 3), 95)
    if gender != "female":
        ml_prostate = predict_prostate(user_profile)
        if ml_prostate is not None:
            hereditary_val = hereditary_risks.get("prostate_cancer", 5)
            blended = round(0.6 * ml_prostate + 0.4 * hereditary_val, 1)
            hereditary_risks["prostate_cancer"] = min(max(blended, 3), 95)
    main_risks = {k: hereditary_risks.get(k, 0) for k in ["breast_cancer", "cervical_cancer", "prostate_cancer", "colorectal_cancer"]}
    if gender == "male":
        main_risks.pop("cervical_cancer", None)
    elif gender == "female":
        main_risks.pop("prostate_cancer", None)
    return {**main_risks, "details": details}


def init_models():
    """Load or train models on startup. If enhanced models exist, use them; else skip (train via python ml_engine.py)."""
    cervical_exists = os.path.exists(os.path.join(MODELS_DIR, "cervical_model.pkl"))
    prostate_exists = os.path.exists(os.path.join(MODELS_DIR, "prostate_model.pkl"))
    if cervical_exists and prostate_exists:
        print("[ML] Pre-trained models loaded.")
    else:
        print("[ML] Run enhanced training: python ml_engine.py (or python train_models.py)")


def main():
    """Run the full enhanced training pipeline and save report."""
    print("GeneShield — Enhanced Training Pipeline for Cervical & Prostate Cancer Models")
    print("=" * 70)
    cervical_results = train_cervical_enhanced()
    prostate_results = train_prostate_enhanced()
    save_cervical_artifacts(cervical_results)
    save_prostate_artifacts(prostate_results)
    write_report(cervical_results, prostate_results)
    print(f"\nDone. Report: reports/{RUN_VERSION}/evaluation_report.md")
    if cervical_results:
        print(f"  Cervical — ROC-AUC: {cervical_results['roc_auc']:.4f}, Recall: {cervical_results['recall']:.4f}")
    if prostate_results:
        print(f"  Prostate — ROC-AUC (LOO): {prostate_results['roc_auc_loo']:.4f}, Accuracy (LOO): {prostate_results['accuracy_loo']:.4f}")


if __name__ == "__main__":
    main()
