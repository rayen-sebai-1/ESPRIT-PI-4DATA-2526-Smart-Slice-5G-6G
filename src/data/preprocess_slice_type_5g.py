"""Preprocessing script for the Slice-Type 5G model (LightGBM multiclass).

Loads raw train_dataset.csv, selects the 6 final features + target (slice Type),
applies a stratified 70/30 train/test split, and LabelEncodes the target.
No feature scaling is applied (tree-based model is scale-invariant).

Outputs:
    data/processed/slice_type_5g_processed.npz  — train/test arrays + metadata
    data/processed/label_encoder_slice_type_5g.pkl — fitted LabelEncoder for inference
"""

import os
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RAW_PATH = "data/raw/train_dataset.csv"
PROCESSED_DIR = "data/processed"
PROCESSED_NPZ = os.path.join(PROCESSED_DIR, "slice_type_5g_processed.npz")
LABEL_ENCODER_PATH = os.path.join(PROCESSED_DIR, "label_encoder_slice_type_5g.pkl")

SELECTED_FEATURES = [
    "LTE/5g Category",
    "Packet Loss Rate",
    "Packet delay",
    "Smartphone",
    "IoT Devices",
    "GBR",
]
TARGET = "slice Type"
CLASS_NAMES = ["eMBB", "mMTC", "URLLC"]

RANDOM_STATE = 12
TRAIN_SIZE = 0.7


# ---------------------------------------------------------------------------
# Main preprocessing function
# ---------------------------------------------------------------------------
def preprocess() -> dict:
    """Run the full Slice-Type-5G preprocessing pipeline.

    Returns:
        dict with keys: X_train, y_train, X_test, y_test, feature_names, classes
    """
    # ------------------------------------------------------------------
    # 1. Load raw data
    # ------------------------------------------------------------------
    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError(
            f"Raw data not found at '{RAW_PATH}'. "
            "Please ensure 'train_dataset.csv' is placed in data/raw/."
        )

    df = pd.read_csv(RAW_PATH)
    print(f"[INFO] Loaded {df.shape[0]} rows, {df.shape[1]} columns from '{RAW_PATH}'.")

    # Validate required columns
    for col in SELECTED_FEATURES + [TARGET]:
        if col not in df.columns:
            raise ValueError(f"Expected column '{col}' not found. Available: {list(df.columns)}")

    # ------------------------------------------------------------------
    # 2. Select features and target
    # ------------------------------------------------------------------
    X = df[SELECTED_FEATURES].copy()
    y = df[TARGET].copy()

    print(f"[INFO] Features: {SELECTED_FEATURES}")
    print(f"[INFO] Target distribution:\n{y.value_counts().to_string()}")

    # ------------------------------------------------------------------
    # 3. Train/test split (stratified, 70/30)
    # ------------------------------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, train_size=TRAIN_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    print(f"[INFO] Train: {X_train.shape[0]} samples | Test: {X_test.shape[0]} samples")

    # ------------------------------------------------------------------
    # 4. Label-encode target (fit on train, transform both)
    # ------------------------------------------------------------------
    label_encoder = LabelEncoder()
    y_train_enc = label_encoder.fit_transform(np.asarray(y_train).ravel())
    y_test_enc = label_encoder.transform(np.asarray(y_test).ravel())

    print(f"[INFO] Encoded classes: {list(label_encoder.classes_)}")
    unique, counts = np.unique(y_train_enc, return_counts=True)
    for cls_idx, cnt in zip(unique, counts):
        print(f"       Class {cls_idx} ({label_encoder.classes_[cls_idx]}): {cnt} samples")

    # ------------------------------------------------------------------
    # 5. Save outputs
    # ------------------------------------------------------------------
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    np.savez(
        PROCESSED_NPZ,
        X_train=X_train.values,
        y_train=y_train_enc,
        X_test=X_test.values,
        y_test=y_test_enc,
        feature_names=np.array(SELECTED_FEATURES),
        classes=np.array(list(label_encoder.classes_)),
    )
    print(f"[INFO] Saved processed data to '{PROCESSED_NPZ}'.")

    joblib.dump(label_encoder, LABEL_ENCODER_PATH)
    print(f"[INFO] Saved label encoder to '{LABEL_ENCODER_PATH}'.")

    return {
        "X_train": X_train.values,
        "y_train": y_train_enc,
        "X_test": X_test.values,
        "y_test": y_test_enc,
        "feature_names": SELECTED_FEATURES,
        "classes": list(label_encoder.classes_),
    }


if __name__ == "__main__":
    preprocess()
