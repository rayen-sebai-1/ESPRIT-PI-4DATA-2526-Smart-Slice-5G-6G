"""Data-quality validation for the processed Congestion 5G dataset.

Checks the processed congestion_5g_processed.npz file for:
  - existence
  - correct feature count/shapes
  - no NaN / Inf values
"""

import os
import sys
import numpy as np

PROCESSED_NPZ = "data/processed/congestion_5g_processed.npz"
EXPECTED_FEATURES = 7
SEQ_LENGTH = 30

def validate() -> bool:
    errors = []

    if not os.path.exists(PROCESSED_NPZ):
        print(f"[FAIL] Processed file not found: '{PROCESSED_NPZ}'")
        return False

    data = np.load(PROCESSED_NPZ, allow_pickle=True)

    required_keys = ["X_train", "y_train", "X_val", "y_val", "X_test", "y_test", "feature_names"]
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing key '{key}' in {PROCESSED_NPZ}.")

    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return False

    X_train = data["X_train"]
    y_train = data["y_train"]
    X_val = data["X_val"]
    
    # Check shapes
    if len(X_train.shape) != 3 or X_train.shape[1] != SEQ_LENGTH or X_train.shape[2] != EXPECTED_FEATURES:
        errors.append(f"Expected train sequence shape (*, {SEQ_LENGTH}, {EXPECTED_FEATURES}), got {X_train.shape}.")

    for name, arr in [("X_train", X_train), ("X_val", X_val)]:
        if np.isnan(arr).any() or np.isinf(arr).any():
            errors.append(f"NaN/Inf values found in {name}.")

    unique_labels = set(np.unique(y_train))
    if not unique_labels.issubset({0, 1}):
        errors.append(f"Unexpected label values: {unique_labels}")

    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return False

    print("[PASS] All Congestion 5G data validation checks passed.")
    print(f"       Train shape: {X_train.shape}, Val shape: {X_val.shape}")
    return True

if __name__ == "__main__":
    ok = validate()
    sys.exit(0 if ok else 1)
