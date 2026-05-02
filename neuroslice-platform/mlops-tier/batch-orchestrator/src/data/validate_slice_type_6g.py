"""Validation script for the processed Slice-Type 6G data.

Loads the processed .npz file and ensures:
1. Shape and minimum data presence.
2. Absence of NaNs / Infs.
3. Feature array size matches the 10 selected features.
4. Exactly 5 slice type target classes are present.
"""

import sys
import numpy as np

NPZ_PATH = "data/processed/slice_type_6g_processed.npz"


def validate_data():
    """Validates the processed 6G Slice Type data arrays."""
    try:
        data = np.load(NPZ_PATH)
    except Exception as e:
        print(f"[ERROR] Could not load data from {NPZ_PATH}: {e}")
        sys.exit(1)

    X_train = data.get("X_train")
    y_train = data.get("y_train")
    X_test = data.get("X_test")
    y_test = data.get("y_test")
    classes = data.get("classes")

    errors = []

    # 1. Basic Shape Validation
    if X_train is None or X_test is None or y_train is None or y_test is None:
        errors.append("One or more train/test arrays are missing from the npz file.")
    else:
        if X_train.shape[0] < 100 or X_test.shape[0] < 100:
            errors.append(
                "Insufficient samples: "
                f"Train ({X_train.shape[0]}), Test ({X_test.shape[0]}). Expected >= 100."
            )
        if X_train.shape[0] != y_train.shape[0]:
            errors.append(
                f"Train shapes mismatch: X({X_train.shape[0]}), y({y_train.shape[0]})."
            )
        if X_test.shape[0] != y_test.shape[0]:
            errors.append(
                f"Test shapes mismatch: X({X_test.shape[0]}), y({y_test.shape[0]})."
            )

        # 2. Number of Features Validation
        expected_feature_count = 10
        if X_train.shape[1] != expected_feature_count:
            errors.append(
                f"Expected {expected_feature_count} features, but got {X_train.shape[1]}."
            )

        # 3. NaNs / Infs Validation
        if np.isnan(X_train).any() or np.isnan(X_test).any():
            errors.append("NaNs detected in the features.")
        if np.isinf(X_train).any() or np.isinf(X_test).any():
            errors.append("Infs detected in the features.")

    # 4. Target Classes Validation
    expected_class_count = 5
    if classes is None:
        errors.append("Classes array missing from the npz metadata.")
    elif len(classes) != expected_class_count:
        errors.append(
            f"Expected {expected_class_count} classes, but found {len(classes)}."
        )

    if errors:
        print("[ERROR] Validation Failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("[INFO] Data validation passed successfully.")


if __name__ == "__main__":
    validate_data()
