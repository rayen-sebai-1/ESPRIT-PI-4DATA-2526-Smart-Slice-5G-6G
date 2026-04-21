"""Unit tests for the 5G Congestion data validation script."""

from unittest import mock

import numpy as np
import pytest

from src.data.validate_congestion_5g import EXPECTED_FEATURES, SEQ_LENGTH, validate


@pytest.fixture
def dummy_processed_npz(tmp_path):
    """Create a temporary valid processed .npz file."""
    processed_path = tmp_path / "congestion_5g_processed.npz"
    # Create valid dummy data
    X_train = np.random.rand(100, SEQ_LENGTH, EXPECTED_FEATURES)
    y_train = np.random.randint(0, 2, size=(100,))
    X_val = np.random.rand(20, SEQ_LENGTH, EXPECTED_FEATURES)
    y_val = np.random.randint(0, 2, size=(20,))
    X_test = np.random.rand(50, SEQ_LENGTH, EXPECTED_FEATURES)
    y_test = np.random.randint(0, 2, size=(50,))
    feature_names = np.array([f"feature_{i}" for i in range(EXPECTED_FEATURES)])

    np.savez(
        processed_path,
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test,
        feature_names=feature_names,
    )
    return str(processed_path)


def test_validate_success(dummy_processed_npz):
    """Validation should pass on a well-formed file."""
    with mock.patch("src.data.validate_congestion_5g.PROCESSED_NPZ", dummy_processed_npz):
        assert validate() is True


def test_validate_missing_file():
    """Validation should fail if the file does not exist."""
    with mock.patch("src.data.validate_congestion_5g.PROCESSED_NPZ", "nonexistent.npz"):
        assert validate() is False


def test_validate_invalid_shapes(tmp_path):
    """Validation should fail if feature dimension is incorrect."""
    invalid_path = tmp_path / "invalid.npz"
    X_train = np.random.rand(100, SEQ_LENGTH, EXPECTED_FEATURES - 1)  # Invalid feature count
    y_train = np.random.randint(0, 2, size=(100,))
    X_val = np.random.rand(20, SEQ_LENGTH, EXPECTED_FEATURES - 1)
    y_val = np.random.randint(0, 2, size=(20,))
    X_test = np.random.rand(50, SEQ_LENGTH, EXPECTED_FEATURES - 1)
    y_test = np.random.randint(0, 2, size=(50,))

    np.savez(
        invalid_path,
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
        X_val=X_val,
        y_val=y_val,
        feature_names=np.array(["a"] * (EXPECTED_FEATURES - 1)),
    )

    with mock.patch("src.data.validate_congestion_5g.PROCESSED_NPZ", str(invalid_path)):
        assert validate() is False
