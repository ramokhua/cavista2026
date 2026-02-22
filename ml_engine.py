"""
GeneShield ML Prediction Engine
================================
- Dataset-trained models for cervical and prostate cancer
- Hereditary cancer risk calculator with Bayesian approach
- Combines ML predictions with epidemiological risk factors
"""

import os
import json
import math
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GridSearchCV
from sklearn.impute import SimpleImputer

warnings.filterwarnings('ignore')

# ============================================
# PATHS
# ============================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MODELS_DIR = os.path.join(BASE_DIR, 'models')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# ============================================
# A) DATASET-TRAINED MODELS
# ============================================

CERVICAL_FEATURES = [
    'Age', 'Number of sexual partners', 'First sexual intercourse',
    'Num of pregnancies', 'Smokes', 'Smokes (years)',
    'Hormonal Contraceptives', 'Hormonal Contraceptives (years)',
    'IUD', 'IUD (years)', 'STDs (number)', 'STDs:HPV', 'STDs:HIV',
    'Dx:Cancer', 'Dx:CIN', 'Dx:HPV'
]

PROSTATE_FEATURES = [
    'radius', 'texture', 'perimeter', 'area',
    'smoothness', 'compactness', 'symmetry', 'fractal_dimension'
]


def _find_csv(filename):
    """Search for CSV in data/ dir or project root."""
    paths = [
        os.path.join(DATA_DIR, filename),
        os.path.join(BASE_DIR, filename),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def train_cervical_model():
    """Train cervical cancer model from cervical-cancer_csv.csv."""
    csv_path = _find_csv('cervical-cancer_csv.csv')
    if not csv_path:
        print('[ML] cervical-cancer_csv.csv not found — skipping cervical model training')
        return False

    print('[ML] Training cervical cancer model...')
    df = pd.read_csv(csv_path)

    # Replace '?' with NaN and convert to numeric
    df = df.replace('?', np.nan)
    for col in CERVICAL_FEATURES + ['Biopsy']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Check target exists
    if 'Biopsy' not in df.columns:
        print('[ML] Biopsy column not found in cervical dataset')
        return False

    # Select available features
    available = [f for f in CERVICAL_FEATURES if f in df.columns]
    X = df[available].copy()
    y = df['Biopsy'].copy()

    # Drop rows with missing target
    mask = y.notna()
    X = X[mask]
    y = y[mask].astype(int)

    # Impute missing features with median
    imputer = SimpleImputer(strategy='median')
    X_imputed = imputer.fit_transform(X)

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    # GridSearchCV with RandomForest
    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [5, 10, None],
        'min_samples_split': [2, 5],
    }
    rf = RandomForestClassifier(class_weight='balanced', random_state=42)
    grid = GridSearchCV(rf, param_grid, cv=3, scoring='f1', n_jobs=-1)
    grid.fit(X_scaled, y)

    best_model = grid.best_estimator_
    print(f'[ML] Cervical model trained — best params: {grid.best_params_}, f1: {grid.best_score_:.3f}')

    # Save model, scaler, imputer, and feature names
    joblib.dump(best_model, os.path.join(MODELS_DIR, 'cervical_model.pkl'))
    joblib.dump(scaler, os.path.join(MODELS_DIR, 'cervical_scaler.pkl'))
    joblib.dump(imputer, os.path.join(MODELS_DIR, 'cervical_imputer.pkl'))
    joblib.dump(available, os.path.join(MODELS_DIR, 'cervical_features.pkl'))

    return True


def train_prostate_model():
    """Train prostate cancer model from Prostate_Cancer.csv."""
    csv_path = _find_csv('Prostate_Cancer.csv')
    if not csv_path:
        print('[ML] Prostate_Cancer.csv not found — skipping prostate model training')
        return False

    print('[ML] Training prostate cancer model...')
    df = pd.read_csv(csv_path)

    # Encode target: M=1, B=0
    target_col = 'diagnosis_result'
    if target_col not in df.columns:
        # Try alternate column names
        for col in df.columns:
            if 'diagnosis' in col.lower():
                target_col = col
                break

    df[target_col] = df[target_col].map({'M': 1, 'B': 0})
    df = df.dropna(subset=[target_col])

    # Select available features
    available = [f for f in PROSTATE_FEATURES if f in df.columns]
    X = df[available].copy()
    y = df[target_col].astype(int)

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # GridSearchCV with GradientBoosting
    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [3, 5],
        'learning_rate': [0.05, 0.1],
    }
    gb = GradientBoostingClassifier(random_state=42)
    grid = GridSearchCV(gb, param_grid, cv=3, scoring='f1', n_jobs=-1)
    grid.fit(X_scaled, y)

    best_model = grid.best_estimator_
    print(f'[ML] Prostate model trained — best params: {grid.best_params_}, f1: {grid.best_score_:.3f}')

    # Save
    joblib.dump(best_model, os.path.join(MODELS_DIR, 'prostate_model.pkl'))
    joblib.dump(scaler, os.path.join(MODELS_DIR, 'prostate_scaler.pkl'))
    joblib.dump(available, os.path.join(MODELS_DIR, 'prostate_features.pkl'))

    return True


def train_all_models():
    """Train all ML models if datasets are available."""
    cervical_ok = train_cervical_model()
    prostate_ok = train_prostate_model()
    return cervical_ok, prostate_ok


def predict_cervical(user_data):
    """Predict cervical cancer probability using trained model."""
    model_path = os.path.join(MODELS_DIR, 'cervical_model.pkl')
    if not os.path.exists(model_path):
        return None

    model = joblib.load(model_path)
    scaler = joblib.load(os.path.join(MODELS_DIR, 'cervical_scaler.pkl'))
    imputer = joblib.load(os.path.join(MODELS_DIR, 'cervical_imputer.pkl'))
    features = joblib.load(os.path.join(MODELS_DIR, 'cervical_features.pkl'))

    # Build feature vector from user data
    row = {}
    age = user_data.get('age', 30)
    row['Age'] = age
    row['Number of sexual partners'] = user_data.get('sexual_partners', np.nan)
    row['First sexual intercourse'] = user_data.get('first_intercourse', np.nan)
    row['Num of pregnancies'] = user_data.get('pregnancies', np.nan)
    row['Smokes'] = 1 if user_data.get('smoke', 'no') in ('yes', 'occasionally') else 0
    row['Smokes (years)'] = user_data.get('smoke_years', 0)
    row['Hormonal Contraceptives'] = user_data.get('hormonal_contraceptives', np.nan)
    row['Hormonal Contraceptives (years)'] = user_data.get('hc_years', np.nan)
    row['IUD'] = user_data.get('iud', np.nan)
    row['IUD (years)'] = user_data.get('iud_years', np.nan)
    row['STDs (number)'] = user_data.get('stds_number', 0)
    row['STDs:HPV'] = user_data.get('stds_hpv', 0)
    row['STDs:HIV'] = user_data.get('stds_hiv', 0)
    row['Dx:Cancer'] = user_data.get('dx_cancer', 0)
    row['Dx:CIN'] = user_data.get('dx_cin', 0)
    row['Dx:HPV'] = user_data.get('dx_hpv', 0)

    X = pd.DataFrame([row])[features]
    X_imputed = imputer.transform(X)
    X_scaled = scaler.transform(X_imputed)

    prob = model.predict_proba(X_scaled)[0][1]
    return round(prob * 100, 1)


def predict_prostate(user_data):
    """Predict prostate cancer probability using trained model."""
    model_path = os.path.join(MODELS_DIR, 'prostate_model.pkl')
    if not os.path.exists(model_path):
        return None

    model = joblib.load(model_path)
    scaler = joblib.load(os.path.join(MODELS_DIR, 'prostate_scaler.pkl'))
    features = joblib.load(os.path.join(MODELS_DIR, 'prostate_features.pkl'))

    # Build feature vector — these come from clinical measurements
    row = {}
    row['radius'] = user_data.get('radius', np.nan)
    row['texture'] = user_data.get('texture', np.nan)
    row['perimeter'] = user_data.get('perimeter', np.nan)
    row['area'] = user_data.get('area', np.nan)
    row['smoothness'] = user_data.get('smoothness', np.nan)
    row['compactness'] = user_data.get('compactness', np.nan)
    row['symmetry'] = user_data.get('symmetry', np.nan)
    row['fractal_dimension'] = user_data.get('fractal_dimension', np.nan)

    # If no clinical data, return None (use hereditary calc instead)
    if all(pd.isna(v) for v in row.values()):
        return None

    X = pd.DataFrame([row])[features]
    X = X.fillna(X.median())
    X_scaled = scaler.transform(X)

    prob = model.predict_proba(X_scaled)[0][1]
    return round(prob * 100, 1)


# ============================================
# B) HEREDITARY CANCER RISK CALCULATOR
# ============================================

# Base population lifetime risk rates (source: ACS, GLOBOCAN)
BASE_RISKS = {
    'breast_cancer': 0.12,       # 12% lifetime risk (women)
    'cervical_cancer': 0.007,    # 0.7% lifetime risk
    'prostate_cancer': 0.12,     # 12% lifetime risk (men)
    'colorectal_cancer': 0.04,   # 4% lifetime risk
    'lung_cancer': 0.06,         # 6% lifetime risk
    'ovarian_cancer': 0.012,     # 1.2% lifetime risk (women)
    'skin_cancer': 0.02,         # 2% lifetime risk (melanoma)
    'stomach_cancer': 0.01,      # 1% lifetime risk
}

# Family history multipliers (epidemiological sources cited)
FAMILY_MULTIPLIERS = {
    'first_degree': {  # parent had it
        'breast_cancer': 2.0,       # Collaborative Group, Lancet 2001
        'cervical_cancer': 1.6,     # Czene et al., Int J Cancer 2002
        'colorectal_cancer': 2.2,   # Butterworth et al., Ann Intern Med 2006
        'prostate_cancer': 2.5,     # Kicinski et al., British J Cancer 2011
        'lung_cancer': 1.5,         # Cote et al., Cancer Epidemiology 2012
        'ovarian_cancer': 1.8,      # Antoniou et al., Am J Hum Genet 2003
        'skin_cancer': 1.7,         # Read et al., J Med Genet 2016
        'stomach_cancer': 1.5,      # Yaghoobi et al., World J Gastroenterol 2010
    },
    'second_degree': {  # grandparent — roughly 50% of first-degree effect
        'breast_cancer': 1.5,
        'cervical_cancer': 1.3,
        'colorectal_cancer': 1.6,
        'prostate_cancer': 1.7,
        'lung_cancer': 1.25,
        'ovarian_cancer': 1.4,
        'skin_cancer': 1.35,
        'stomach_cancer': 1.25,
    },
    'both_parents': {  # dramatically higher
        'breast_cancer': 4.0,
        'cervical_cancer': 2.5,
        'colorectal_cancer': 4.0,
        'prostate_cancer': 5.0,
        'lung_cancer': 2.5,
        'ovarian_cancer': 3.0,
        'skin_cancer': 2.5,
        'stomach_cancer': 2.5,
    }
}

# Age modifiers
AGE_MODIFIERS = {
    (0, 29): 0.5,
    (30, 44): 1.0,
    (45, 59): 1.8,
    (60, 120): 2.5,
}

# Gender-specific cancers
FEMALE_ONLY = {'cervical_cancer', 'ovarian_cancer'}
MALE_ONLY = {'prostate_cancer'}
FEMALE_HIGHER = {'breast_cancer'}  # men can get it but much rarer


def _get_age_modifier(age):
    for (lo, hi), mod in AGE_MODIFIERS.items():
        if lo <= age <= hi:
            return mod
    return 1.0


def _get_lifestyle_modifier(profile):
    """Calculate lifestyle risk modifier from profile data."""
    modifier = 1.0
    factors = []

    smoke = (profile.get('smoke') or '').lower()
    if smoke in ('yes', 'current', 'regularly'):
        modifier *= 1.40  # +40% cancer risk overall
        factors.append('Smoking (+40% risk)')
    elif smoke == 'occasionally':
        modifier *= 1.15
        factors.append('Occasional smoking (+15% risk)')

    # BMI
    weight = float(profile.get('weight') or 0)
    height = float(profile.get('height') or 0)
    bmi = 0
    if weight > 0 and height > 0:
        bmi = weight / ((height / 100) ** 2)
        if bmi > 30:
            modifier *= 1.25  # +25% obesity risk
            factors.append(f'Obesity BMI {bmi:.1f} (+25% risk)')
        elif bmi > 25:
            modifier *= 1.10
            factors.append(f'Overweight BMI {bmi:.1f} (+10% risk)')

    exercise = (profile.get('exercise') or '').lower()
    if exercise in ('never', 'none', 'sedentary'):
        modifier *= 1.25  # +25% no exercise
        factors.append('No exercise (+25% risk)')
    elif exercise in ('rarely', 'light'):
        modifier *= 1.10
        factors.append('Rare exercise (+10% risk)')

    alcohol = (profile.get('alcohol') or '').lower()
    if alcohol in ('yes', 'regularly', 'heavy', 'daily'):
        modifier *= 1.20  # +20% heavy alcohol
        factors.append('Regular alcohol (+20% risk)')
    elif alcohol == 'occasionally':
        modifier *= 1.05
        factors.append('Occasional alcohol (+5% risk)')

    diet = (profile.get('diet') or '').lower()
    if diet in ('excellent', 'very healthy', 'good'):
        modifier *= 0.88  # -12% good diet
        factors.append('Good diet (-12% risk)')
    elif diet in ('poor', 'unhealthy'):
        modifier *= 1.15
        factors.append('Poor diet (+15% risk)')

    return modifier, factors, bmi


def _get_family_multiplier(cancer_type, father_history, mother_history, grand_history):
    """Determine the appropriate family multiplier for a cancer type."""
    father_has = cancer_type in father_history
    mother_has = cancer_type in mother_history
    grand_has = cancer_type in grand_history

    if father_has and mother_has:
        return FAMILY_MULTIPLIERS['both_parents'].get(cancer_type, 3.0), 'both parents'
    elif father_has or mother_has:
        return FAMILY_MULTIPLIERS['first_degree'].get(cancer_type, 1.5), 'one parent'
    elif grand_has:
        return FAMILY_MULTIPLIERS['second_degree'].get(cancer_type, 1.3), 'grandparent'
    else:
        return 1.0, 'none'


def calculate_hereditary_risk(user_profile):
    """
    Calculate hereditary cancer risk using Bayesian approach with real
    epidemiological multipliers.

    Formula: P(disease) = 1 - (1 - base_risk) ^ (family_multiplier * lifestyle_modifier * age_modifier)
    """
    # Parse profile data
    gender = (user_profile.get('gender') or '').lower()
    dob = user_profile.get('dob')
    age = 35  # default
    if dob:
        try:
            birth = datetime.strptime(str(dob), '%Y-%m-%d')
            age = (datetime.now() - birth).days // 365
        except (ValueError, TypeError):
            pass

    # Parse family history
    father_h = user_profile.get('fatherHistory') or user_profile.get('father_history') or []
    mother_h = user_profile.get('motherHistory') or user_profile.get('mother_history') or []
    grand_h = user_profile.get('grandHistory') or user_profile.get('grand_history') or []

    if isinstance(father_h, str):
        try: father_h = json.loads(father_h)
        except: father_h = []
    if isinstance(mother_h, str):
        try: mother_h = json.loads(mother_h)
        except: mother_h = []
    if isinstance(grand_h, str):
        try: grand_h = json.loads(grand_h)
        except: grand_h = []

    age_mod = _get_age_modifier(age)
    lifestyle_mod, lifestyle_factors, bmi = _get_lifestyle_modifier(user_profile)

    results = {}
    family_analysis = {}

    for cancer_type, base_risk in BASE_RISKS.items():
        # Gender filtering
        if cancer_type in FEMALE_ONLY and gender == 'male':
            continue
        if cancer_type in MALE_ONLY and gender == 'female':
            continue
        if cancer_type in FEMALE_HIGHER and gender == 'male':
            base_risk *= 0.01  # 1% of female rate for men

        fam_mult, fam_source = _get_family_multiplier(
            cancer_type, father_h, mother_h, grand_h
        )

        # Cancer-specific lifestyle adjustments
        cancer_lifestyle_mod = lifestyle_mod
        if cancer_type == 'breast_cancer' and bmi > 30:
            cancer_lifestyle_mod *= 1.05  # extra +5% for breast
        if cancer_type == 'colorectal_cancer':
            diet = (user_profile.get('diet') or '').lower()
            if diet in ('excellent', 'good'):
                cancer_lifestyle_mod *= 0.85  # fibre-rich diet helps colorectal
            elif diet == 'poor':
                cancer_lifestyle_mod *= 1.10  # red meat, processed food

        # Bayesian formula
        combined_mult = fam_mult * cancer_lifestyle_mod * age_mod
        risk = 1 - (1 - base_risk) ** combined_mult
        risk_pct = round(min(max(risk * 100, 3), 95), 1)

        results[cancer_type] = risk_pct

        family_analysis[cancer_type] = {
            'risk_percent': risk_pct,
            'base_risk': round(base_risk * 100, 2),
            'family_multiplier': round(fam_mult, 2),
            'family_source': fam_source,
            'age_modifier': round(age_mod, 2),
            'lifestyle_modifier': round(cancer_lifestyle_mod, 2),
            'combined_multiplier': round(combined_mult, 2),
        }

    return results, {
        'family_analysis': family_analysis,
        'lifestyle_factors': lifestyle_factors,
        'lifestyle_multiplier': round(lifestyle_mod, 2),
        'bmi': round(bmi, 1) if bmi > 0 else None,
        'age': age,
        'gender': gender,
    }


# ============================================
# C) COMBINED RISK CALCULATION
# ============================================

def calculate_all_risks(user_profile):
    """
    Combine hereditary risk calculator with ML model predictions.
    Returns cancer risk percentages and detailed analysis.
    """
    # Get hereditary risks first
    hereditary_risks, details = calculate_hereditary_risk(user_profile)

    # Try ML predictions for cervical and prostate
    gender = (user_profile.get('gender') or '').lower()
    age = details.get('age', 35)

    # Cervical cancer ML prediction (females only)
    if gender != 'male':
        ml_cervical = predict_cervical({
            'age': age,
            'smoke': user_profile.get('smoke', 'no'),
        })
        if ml_cervical is not None:
            # Blend: 60% ML + 40% hereditary
            hereditary_val = hereditary_risks.get('cervical_cancer', 5)
            blended = round(0.6 * ml_cervical + 0.4 * hereditary_val, 1)
            hereditary_risks['cervical_cancer'] = min(max(blended, 3), 95)
            details['family_analysis'].setdefault('cervical_cancer', {})
            details['family_analysis']['cervical_cancer']['ml_prediction'] = ml_cervical
            details['family_analysis']['cervical_cancer']['blend'] = '60% ML + 40% hereditary'

    # Prostate cancer ML prediction (males only)
    if gender != 'female':
        ml_prostate = predict_prostate(user_profile)
        if ml_prostate is not None:
            hereditary_val = hereditary_risks.get('prostate_cancer', 5)
            blended = round(0.6 * ml_prostate + 0.4 * hereditary_val, 1)
            hereditary_risks['prostate_cancer'] = min(max(blended, 3), 95)
            details['family_analysis'].setdefault('prostate_cancer', {})
            details['family_analysis']['prostate_cancer']['ml_prediction'] = ml_prostate
            details['family_analysis']['prostate_cancer']['blend'] = '60% ML + 40% hereditary'

    # Return the 4 main cancer types for the dashboard
    main_risks = {
        'breast_cancer': hereditary_risks.get('breast_cancer', 0),
        'cervical_cancer': hereditary_risks.get('cervical_cancer', 0),
        'prostate_cancer': hereditary_risks.get('prostate_cancer', 0),
        'colorectal_cancer': hereditary_risks.get('colorectal_cancer', 0),
    }

    # Filter by gender
    if gender == 'male':
        main_risks.pop('cervical_cancer', None)
        main_risks.pop('ovarian_cancer', None)
    elif gender == 'female':
        main_risks.pop('prostate_cancer', None)

    return {
        **main_risks,
        'details': details,
    }


# ============================================
# INITIALIZATION
# ============================================

def init_models():
    """Train models on startup if datasets exist and models don't."""
    cervical_exists = os.path.exists(os.path.join(MODELS_DIR, 'cervical_model.pkl'))
    prostate_exists = os.path.exists(os.path.join(MODELS_DIR, 'prostate_model.pkl'))

    if not cervical_exists or not prostate_exists:
        print('[ML] Training models on first run...')
        train_all_models()
    else:
        print('[ML] Pre-trained models loaded.')


if __name__ == '__main__':
    # Test with sample profile
    init_models()
    test_profile = {
        'gender': 'Female',
        'dob': '1985-06-15',
        'height': 165,
        'weight': 72,
        'smoke': 'no',
        'alcohol': 'occasionally',
        'exercise': 'sometimes',
        'diet': 'average',
        'fatherHistory': ['colorectal_cancer'],
        'motherHistory': ['breast_cancer'],
        'grandHistory': ['breast_cancer', 'cervical_cancer'],
    }
    results = calculate_all_risks(test_profile)
    print('\n=== Risk Assessment Results ===')
    for k, v in results.items():
        if k != 'details':
            print(f'  {k}: {v}%')
    print('\n=== Details ===')
    print(json.dumps(results['details'], indent=2))
