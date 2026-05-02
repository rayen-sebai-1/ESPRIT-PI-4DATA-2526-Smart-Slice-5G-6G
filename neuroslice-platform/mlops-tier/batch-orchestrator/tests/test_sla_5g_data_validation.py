"""Data-quality tests for the processed SLA dataset."""

import os

import numpy as np
import pytest

PROCESSED_NPZ = "data/processed/sla_5g_processed.npz"
EXPECTED_FEATURES = 5
MIN_TRAIN_ROWS = 100
MIN_TEST_ROWS = 50


def _load_data():
    if not os.path.exists(PROCESSED_NPZ):
        pytest.skip(
            f"Processed file not found at '{PROCESSED_NPZ}'. "
            "Run 'python src/data/preprocess_sla_5g.py' first."
        )
    return np.load(PROCESSED_NPZ, allow_pickle=True)


class TestProcessedSLAData:
    """Data tests for the processed SLA dataset."""

    def test_required_arrays_present(self):
        """The .npz must contain all required arrays."""
        data = _load_data()
        for key in ["X_train", "y_train", "X_test", "y_test", "feature_names"]:
            assert key in data, f"Missing key: '{key}'"

    def test_no_nan_values(self):
        """Processed arrays must not contain NaN values."""
        data = _load_data()
        for key in ["X_train", "X_test"]:
            arr = data[key]
            assert not np.isnan(arr).any(), f"NaN values found in {key}"

    def test_no_inf_values(self):
        """Processed arrays must not contain Inf values."""
        data = _load_data()
        for key in ["X_train", "X_test"]:
            arr = data[key]
            assert not np.isinf(arr).any(), f"Inf values found in {key}"

    def test_correct_feature_count(self):
        """Feature arrays must have exactly 5 columns."""
        data = _load_data()
        assert data["X_train"].shape[1] == EXPECTED_FEATURES, (
            f"Expected {EXPECTED_FEATURES} features in X_train, "
            f"got {data['X_train'].shape[1]}"
        )
        assert data["X_test"].shape[1] == EXPECTED_FEATURES, (
            f"Expected {EXPECTED_FEATURES} features in X_test, "
            f"got {data['X_test'].shape[1]}"
        )

    def test_train_row_count(self):
        """Train set must have more than MIN_TRAIN_ROWS rows."""
        data = _load_data()
        assert (
            len(data["X_train"]) > MIN_TRAIN_ROWS
        ), f"Train rows {len(data['X_train'])} < minimum {MIN_TRAIN_ROWS}"

    def test_test_row_count(self):
        """Test set must have more than MIN_TEST_ROWS rows."""
        data = _load_data()
        assert (
            len(data["X_test"]) > MIN_TEST_ROWS
        ), f"Test rows {len(data['X_test'])} < minimum {MIN_TEST_ROWS}"

    def test_labels_are_binary(self):
        """Labels must be 0 or 1."""
        data = _load_data()
        for key in ["y_train", "y_test"]:
            unique = set(np.unique(data[key]))
            assert unique.issubset({0, 1}), f"Unexpected labels in {key}: {unique}"
