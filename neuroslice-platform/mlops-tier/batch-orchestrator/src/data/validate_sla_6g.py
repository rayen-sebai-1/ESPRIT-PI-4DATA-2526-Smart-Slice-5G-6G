"""Data-quality validation for the processed SLA-6G dataset.

Checks the processed sla_6g .npz file for:
  - existence
  - correct feature count (14)
  - no NaN / Inf values
  - minimum row count
  - binary label values {0, 1}
"""

import os
import sys

import numpy as np

PROCESSED_NPZ = "data/processed/sla_6g_processed.npz"
EXPECTED_FEATURES = 14
MIN_TRAIN_ROWS = 100
MIN_TEST_ROWS = 50


def validate() -> bool:
    """Run all validation checks. Returns True if all pass."""
    errors = []

    # ------------------------------------------------------------------
    # 1. File existence
    # ------------------------------------------------------------------
    if not os.path.exists(PROCESSED_NPZ):
        print(f"[FAIL] Processed file not found: '{PROCESSED_NPZ}'")
        print("       Run 'python src/data/preprocess_sla_6g.py' first.")
        return False

    data = np.load(PROCESSED_NPZ, allow_pickle=True)

    # ------------------------------------------------------------------
    # 2. Required arrays
    # ------------------------------------------------------------------
    required_keys = ["X_train", "y_train", "X_test", "y_test", "feature_names"]
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing key '{key}' in {PROCESSED_NPZ}.")

    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return False

    X_train = data["X_train"]
    y_train = data["y_train"]
    X_test = data["X_test"]
    y_test = data["y_test"]
    feature_names = data["feature_names"]

    # ------------------------------------------------------------------
    # 3. Feature count
    # ------------------------------------------------------------------
    if X_train.shape[1] != EXPECTED_FEATURES:
        errors.append(f"Expected {EXPECTED_FEATURES} features, got {X_train.shape[1]}.")

    if len(feature_names) != EXPECTED_FEATURES:
        errors.append(
            f"Expected {EXPECTED_FEATURES} feature names, got {len(feature_names)}."
        )

    # ------------------------------------------------------------------
    # 4. No NaN / Inf
    # ------------------------------------------------------------------
    for name, arr in [("X_train", X_train), ("X_test", X_test)]:
        if np.isnan(arr).any():
            errors.append(f"NaN values found in {name}.")
        if np.isinf(arr).any():
            errors.append(f"Inf values found in {name}.")

    for name, arr in [("y_train", y_train), ("y_test", y_test)]:
        if np.isnan(arr.astype(float)).any():
            errors.append(f"NaN values found in {name}.")

    # ------------------------------------------------------------------
    # 5. Minimum row count
    # ------------------------------------------------------------------
    if len(X_train) < MIN_TRAIN_ROWS:
        errors.append(f"Train set too small: {len(X_train)} < {MIN_TRAIN_ROWS}.")
    if len(X_test) < MIN_TEST_ROWS:
        errors.append(f"Test set too small: {len(X_test)} < {MIN_TEST_ROWS}.")

    # ------------------------------------------------------------------
    # 6. Label values must be binary
    # ------------------------------------------------------------------
    unique_labels = set(np.unique(y_train)) | set(np.unique(y_test))
    if not unique_labels.issubset({0, 1}):
        errors.append(f"Unexpected label values: {unique_labels}")

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return False

    print("[PASS] All SLA-6G data validation checks passed.")
    print(f"       Train shape: {X_train.shape}, Test shape: {X_test.shape}")
    print(f"       Features ({len(feature_names)}): {list(feature_names)}")
    return True


if __name__ == "__main__":
    ok = validate()
    sys.exit(0 if ok else 1)
