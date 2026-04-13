"""Preprocessing script for the Slice-Type 6G model (XGBoost multiclass).

Loads raw 6G_prepared.csv, selects final budget and connection features + target (Slice Type),
applies a stratified 80/20 train/test split, LabelEncodes the target, maps boolean strings,
and artificially injects 5% label noise ONLY into the training set to prevent trivial
deterministic model solutions as identified in EDA.

Outputs:
    data/processed/slice_type_6g_processed.npz  — train/test arrays + metadata
    data/processed/label_encoder_slice_type_6g.pkl — fitted LabelEncoder for inference
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
RAW_PATH = "data/raw/6G_prepared.csv"
PROCESSED_DIR = "data/processed"
PROCESSED_NPZ = os.path.join(PROCESSED_DIR, "slice_type_6g_processed.npz")
LABEL_ENCODER_PATH = os.path.join(PROCESSED_DIR, "label_encoder_slice_type_6g.pkl")

SELECTED_FEATURES = [
    "Packet Loss Budget",
    "Latency Budget (ns)",
    "Jitter Budget (ns)",
    "Data Rate Budget (Gbps)",
    "Required Mobility",
    "Required Connectivity",
    "Slice Available Transfer Rate (Gbps)",
    "Slice Latency (ns)",
    "Slice Packet Loss",
    "Slice Jitter (ns)",
]
TARGET = "Slice Type"

RANDOM_STATE = 42
TRAIN_SIZE = 0.80
LABEL_NOISE_RATE = 0.05  # 5% artificial label noise


# ---------------------------------------------------------------------------
# Main preprocessing function
# ---------------------------------------------------------------------------
def preprocess() -> dict:
    """Run the full Slice-Type-6G preprocessing pipeline.

    Returns:
        dict with keys: X_train, y_train, X_test, y_test, feature_names, classes
    """
    # 1. Load raw data
    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError(
            f"Raw data not found at '{RAW_PATH}'. "
            "Please ensure '6G_prepared.csv' is placed in data/raw/."
        )

    df = pd.read_csv(RAW_PATH)
    print(f"[INFO] Loaded {df.shape[0]} rows, {df.shape[1]} columns from '{RAW_PATH}'.")

    # 2. Validate required columns
    for col in SELECTED_FEATURES + [TARGET]:
        if col not in df.columns:
            raise ValueError(f"Expected column '{col}' not found. Available: {list(df.columns)}")

    X = df[SELECTED_FEATURES].copy()
    y = df[TARGET].copy()

    # Map yes/no strings to 1/0
    bool_map = {"yes": 1, "no": 0}
    for bool_col in ["Required Mobility", "Required Connectivity"]:
        if X[bool_col].dtype == object:
            X[bool_col] = X[bool_col].str.lower().map(bool_map)
            
    # Quick fill of any NaNs in the budget features (e.g. Packet Loss Budget has some nulls in EDA)
    for col in X.columns:
        if X[col].isnull().any():
            print(f"[WARN] Imputing missing values in {col} with 0.0")
            X[col] = X[col].fillna(0.0)

    print(f"[INFO] Target distribution:\\n{y.value_counts().to_string()}")

    # 3. Label-encode target
    label_encoder = LabelEncoder()
    y_enc = label_encoder.fit_transform(np.asarray(y).ravel())
    print(f"[INFO] Encoded classes: {list(label_encoder.classes_)}")

    # 4. Train/test split (stratified)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc, train_size=TRAIN_SIZE, random_state=RANDOM_STATE, stratify=y_enc
    )
    print(f"[INFO] Train: {X_train.shape[0]} samples | Test: {X_test.shape[0]} samples")

    # 5. Add synthetic label noise exclusively to the training set
    num_train = len(y_train)
    num_noise = int(num_train * LABEL_NOISE_RATE)
    
    np.random.seed(RANDOM_STATE)
    noise_indices = np.random.choice(num_train, size=num_noise, replace=False)
    
    y_train_noisy = y_train.copy()
    unique_classes = np.arange(len(label_encoder.classes_))
    
    actually_flipped = 0
    for idx in noise_indices:
        original_class = y_train[idx]
        available_classes = np.delete(unique_classes, original_class)
        new_class = np.random.choice(available_classes)
        y_train_noisy[idx] = new_class
        actually_flipped += 1
        
    print(f"[INFO] Injected {LABEL_NOISE_RATE*100:.0f}% label noise.")
    print(f"[INFO] {actually_flipped} labels were artificially flipped in the training set.")

    # 6. Save outputs
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    np.savez(
        PROCESSED_NPZ,
        X_train=X_train.values.astype(np.float32),
        y_train=y_train_noisy,
        X_test=X_test.values.astype(np.float32),
        y_test=y_test,
        feature_names=np.array(SELECTED_FEATURES),
        classes=np.array(list(label_encoder.classes_)),
    )
    print(f"[INFO] Saved processed data to '{PROCESSED_NPZ}'.")

    joblib.dump(label_encoder, LABEL_ENCODER_PATH)
    print(f"[INFO] Saved label encoder to '{LABEL_ENCODER_PATH}'.")

    return {
        "X_train": X_train.values.astype(np.float32),
        "y_train": y_train_noisy,
        "X_test": X_test.values.astype(np.float32),
        "y_test": y_test,
        "feature_names": SELECTED_FEATURES,
        "classes": list(label_encoder.classes_),
    }


if __name__ == "__main__":
    preprocess()
