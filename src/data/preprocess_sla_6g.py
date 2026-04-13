"""Preprocessing script for the SLA 6G adherence model.

Loads raw 6G CSV, engineers temporal QoS features (lag-1, rolling mean/std),
encodes categorical context columns, applies stratified train/test split,
StandardScaler (fit on train only), and SMOTE oversampling on the train set.

6G SLA thresholds per slice type (used to create sla_met when absent or
all-same-class):
    ERLLC  — latency ≤ 1 ms,  loss ≤ 1e-5, jitter ≤ 0.5 ms
    mURLLC — latency ≤ 1 ms,  loss ≤ 1e-4, jitter ≤ 1 ms
    MBRLLC — latency ≤ 5 ms,  loss ≤ 1e-3, jitter ≤ 2 ms
    feMBB  — latency ≤ 10 ms, loss ≤ 1e-2, jitter ≤ 5 ms
    umMTC  — latency ≤ 100 ms,loss ≤ 1e-2, jitter ≤ 10 ms

Outputs:
    data/processed/sla_6g_processed.npz  — train/test arrays + metadata
    data/processed/scaler_sla_6g.pkl     — fitted StandardScaler for inference
    data/processed/encoders_sla_6g.pkl   — fitted LabelEncoders for inference
"""

import os
import warnings

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RAW_PATH = "data/raw/6G_prepared.csv"
PROCESSED_DIR = "data/processed"
PROCESSED_NPZ = os.path.join(PROCESSED_DIR, "sla_6g_processed.npz")
SCALER_PATH = os.path.join(PROCESSED_DIR, "scaler_sla_6g.pkl")
ENCODERS_PATH = os.path.join(PROCESSED_DIR, "encoders_sla_6g.pkl")

# SLA QoS thresholds per 6G slice type (all times in nanoseconds)
SLA_THRESHOLDS_6G = {
    "ERLLC":  {"latency_max_ns": 1_000_000,    "loss_max": 0.00001, "jitter_max_ns": 500_000},
    "mURLLC": {"latency_max_ns": 1_000_000,    "loss_max": 0.0001,  "jitter_max_ns": 1_000_000},
    "MBRLLC": {"latency_max_ns": 5_000_000,    "loss_max": 0.001,   "jitter_max_ns": 2_000_000},
    "feMBB":  {"latency_max_ns": 10_000_000,   "loss_max": 0.01,    "jitter_max_ns": 5_000_000},
    "umMTC":  {"latency_max_ns": 100_000_000,  "loss_max": 0.01,    "jitter_max_ns": 10_000_000},
}

# QoS columns used for temporal feature engineering
QOS_COLS = ["Slice Latency (ns)", "Slice Packet Loss", "Slice Jitter (ns)"]
ROLLING_WINDOW = 5

# Categorical columns to label-encode
CATEGORICAL_COLS = {
    "Slice Type":             "Slice Type Encoded",
    "Required Mobility":      "Mobility Encoded",
    "Required Connectivity":  "Connectivity Encoded",
    "Slice Handover":         "Handover Encoded",
}

# Final 14 feature columns fed to the model
FINAL_FEATURES = [
    # Temporal QoS — 9 features (no same-row leakage: all shifted)
    "Slice Latency (ns)_lag1",
    "Slice Latency (ns)_rolling_mean",
    "Slice Latency (ns)_rolling_std",
    "Slice Packet Loss_lag1",
    "Slice Packet Loss_rolling_mean",
    "Slice Packet Loss_rolling_std",
    "Slice Jitter (ns)_lag1",
    "Slice Jitter (ns)_rolling_mean",
    "Slice Jitter (ns)_rolling_std",
    # Context — 5 features
    "Slice Type Encoded",
    "Mobility Encoded",
    "Connectivity Encoded",
    "Handover Encoded",
    "Slice Available Transfer Rate (Gbps)",
]

TARGET = "sla_met"
RANDOM_STATE = 42
TEST_SIZE = 0.2


# ---------------------------------------------------------------------------
# Helper: compute sla_met from per-slice QoS thresholds
# ---------------------------------------------------------------------------
def _compute_sla_met(row: pd.Series) -> int:
    """Return 1 if the session meets its 6G SLA, 0 otherwise."""
    slice_type = row["Slice Type"]
    if slice_type not in SLA_THRESHOLDS_6G:
        return 0
    th = SLA_THRESHOLDS_6G[slice_type]
    return int(
        row["Slice Latency (ns)"] <= th["latency_max_ns"]
        and row["Slice Packet Loss"] <= th["loss_max"]
        and row["Slice Jitter (ns)"] <= th["jitter_max_ns"]
    )


# ---------------------------------------------------------------------------
# Main preprocessing function
# ---------------------------------------------------------------------------
def preprocess() -> dict:
    """Run the full SLA-6G preprocessing pipeline.

    Returns:
        dict with keys: X_train, y_train, X_test, y_test, feature_names
    """
    # ------------------------------------------------------------------
    # 1. Load raw data
    # ------------------------------------------------------------------
    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError(
            f"Raw data not found at '{RAW_PATH}'. "
            "Please ensure '6G_prepared.csv' is placed in data/raw/."
        )

    df = pd.read_csv(RAW_PATH)
    print(f"[INFO] Loaded {df.shape[0]} rows, {df.shape[1]} columns from '{RAW_PATH}'.")

    # ------------------------------------------------------------------
    # 2. Ensure target column exists (create synthetically if needed)
    # ------------------------------------------------------------------
    if TARGET not in df.columns or df[TARGET].nunique() <= 1:
        print("[INFO] Creating synthetic 'sla_met' target from 6G QoS thresholds...")
        df[TARGET] = df.apply(_compute_sla_met, axis=1)

    print(f"[INFO] Target distribution: {dict(df[TARGET].value_counts())}")

    # ------------------------------------------------------------------
    # 3. Label-encode categorical context columns
    # ------------------------------------------------------------------
    encoders: dict[str, LabelEncoder] = {}
    for src_col, enc_col in CATEGORICAL_COLS.items():
        if src_col not in df.columns:
            raise ValueError(f"Expected column '{src_col}' not found. Available: {list(df.columns)}")
        le = LabelEncoder()
        df[enc_col] = le.fit_transform(df[src_col].astype(str))
        encoders[enc_col] = le
        print(f"[INFO] Encoded '{src_col}' -> '{enc_col}': {list(le.classes_)}")

    # ------------------------------------------------------------------
    # 4. Sort by Slice Type to create meaningful temporal sequences
    #    (necessary so lag/rolling features are meaningful within each slice)
    # ------------------------------------------------------------------
    df = df.sort_values(["Slice Type", "Slice Available Transfer Rate (Gbps)"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    # 5. Temporal feature engineering (lag-1, rolling mean/std)
    #    All use shift(1) so the same row's QoS is never used as a feature,
    #    preventing data leakage.
    # ------------------------------------------------------------------
    for col in QOS_COLS:
        grp = df.groupby("Slice Type")[col]
        df[f"{col}_lag1"] = grp.shift(1)
        df[f"{col}_rolling_mean"] = grp.transform(
            lambda x: x.shift(1).rolling(ROLLING_WINDOW, min_periods=1).mean()
        )
        df[f"{col}_rolling_std"] = grp.transform(
            lambda x: x.shift(1).rolling(ROLLING_WINDOW, min_periods=2).std()
        )

    rows_before = len(df)
    df = df.dropna(subset=FINAL_FEATURES).reset_index(drop=True)
    print(f"[INFO] Dropped {rows_before - len(df)} rows with NaN lag features.")
    print(f"[INFO] Dataset after feature engineering: {df.shape}")

    # Validate all required features are present
    missing = [f for f in FINAL_FEATURES if f not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns after engineering: {missing}")

    # ------------------------------------------------------------------
    # 6. Select features and target
    # ------------------------------------------------------------------
    X = df[FINAL_FEATURES].copy()
    y = df[TARGET].copy()

    print(f"[INFO] Features: {FINAL_FEATURES}")
    print(f"[INFO] Target distribution after engineering: {dict(y.value_counts())}")

    # ------------------------------------------------------------------
    # 7. Train/test split (stratified)
    # ------------------------------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    print(f"[INFO] Train: {X_train.shape[0]} samples | Test: {X_test.shape[0]} samples")

    # ------------------------------------------------------------------
    # 8. StandardScaler (fit on train only)
    # ------------------------------------------------------------------
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # ------------------------------------------------------------------
    # 9. SMOTE on train set only
    # ------------------------------------------------------------------
    smote = SMOTE(random_state=RANDOM_STATE)
    X_train_res, y_train_res = smote.fit_resample(X_train_scaled, y_train)

    print(f"[INFO] After SMOTE — Train: {X_train_res.shape[0]} samples")
    print(f"[INFO] Class distribution after SMOTE: {dict(pd.Series(y_train_res).value_counts())}")

    # ------------------------------------------------------------------
    # 10. Save outputs
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

    joblib.dump(encoders, ENCODERS_PATH)
    print(f"[INFO] Saved label encoders to '{ENCODERS_PATH}'.")

    return {
        "X_train": X_train_res,
        "y_train": y_train_res,
        "X_test": X_test_scaled,
        "y_test": y_test.values,
        "feature_names": FINAL_FEATURES,
    }


if __name__ == "__main__":
    preprocess()
