"""Preprocessing script for the SLA 5G adherence model (Model B).

Loads raw 5G CSV, selects the 5 final features + target (sla_met),
applies stratified train/test split, StandardScaler (fit on train only),
and SMOTE oversampling on the train set.

Outputs:
    data/processed/sla_5g_processed.npz  — train/test arrays + metadata
    data/processed/scaler_sla_5g.pkl     — fitted StandardScaler for inference
"""

import os
import warnings

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RAW_PATH = "data/raw/5G_prepared.csv"
PROCESSED_DIR = "data/processed"
PROCESSED_NPZ = os.path.join(PROCESSED_DIR, "sla_5g_processed.npz")
SCALER_PATH = os.path.join(PROCESSED_DIR, "scaler_sla_5g.pkl")

FINAL_FEATURES = [
    "Packet Loss Rate",
    "Packet delay",
    "Smart City & Home",
    "IoT Devices",
    "Public Safety",
]
TARGET = "sla_met"

RANDOM_STATE = 42
TEST_SIZE = 0.2


# ---------------------------------------------------------------------------
# Main preprocessing function
# ---------------------------------------------------------------------------
def preprocess() -> dict:
    """Run the full SLA preprocessing pipeline.

    Returns:
        dict with keys: X_train, y_train, X_test, y_test, feature_names
    """
    # ------------------------------------------------------------------
    # 1. Load raw data
    # ------------------------------------------------------------------
    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError(
            f"Raw data not found at '{RAW_PATH}'. " "Please ensure '5G_prepared.csv' is placed in data/raw/."
        )

    df = pd.read_csv(RAW_PATH)
    print(f"[INFO] Loaded {df.shape[0]} rows, {df.shape[1]} columns from '{RAW_PATH}'.")

    # Validate required columns
    for col in FINAL_FEATURES + [TARGET]:
        if col not in df.columns:
            raise ValueError(f"Expected column '{col}' not found. Available: {list(df.columns)}")

    # ------------------------------------------------------------------
    # 2. Select features and target
    # ------------------------------------------------------------------
    X = df[FINAL_FEATURES].copy()
    y = df[TARGET].copy()

    print(f"[INFO] Features: {FINAL_FEATURES}")
    print(f"[INFO] Target distribution: {dict(y.value_counts())}")

    # ------------------------------------------------------------------
    # 3. Train/test split (stratified)
    # ------------------------------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    print(f"[INFO] Train: {X_train.shape[0]} samples | Test: {X_test.shape[0]} samples")

    # ------------------------------------------------------------------
    # 4. StandardScaler (fit on train only)
    # ------------------------------------------------------------------
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # ------------------------------------------------------------------
    # 5. SMOTE (train only)
    # ------------------------------------------------------------------
    smote = SMOTE(random_state=RANDOM_STATE)
    X_train_res, y_train_res = smote.fit_resample(X_train_scaled, y_train)

    print(f"[INFO] After SMOTE — Train: {X_train_res.shape[0]} samples")
    print(f"[INFO] Class distribution after SMOTE: {dict(pd.Series(y_train_res).value_counts())}")

    # ------------------------------------------------------------------
    # 6. Save outputs
    # ------------------------------------------------------------------
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    np.savez(
        PROCESSED_NPZ,
        X_train=X_train_res,
        y_train=y_train_res,
        X_test=X_test_scaled,
        y_test=y_test.values,
        feature_names=np.array(FINAL_FEATURES),
    )
    print(f"[INFO] Saved processed data to '{PROCESSED_NPZ}'.")

    joblib.dump(scaler, SCALER_PATH)
    print(f"[INFO] Saved scaler to '{SCALER_PATH}'.")

    return {
        "X_train": X_train_res,
        "y_train": y_train_res,
        "X_test": X_test_scaled,
        "y_test": y_test.values,
        "feature_names": FINAL_FEATURES,
    }


if __name__ == "__main__":
    preprocess()
