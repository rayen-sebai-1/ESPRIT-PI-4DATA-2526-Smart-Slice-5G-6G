"""Data-quality tests for the processed 6G CSV."""

import os
import pytest
import pandas as pd

PROCESSED_PATH = "data/processed/6g_processed.csv"
NORMALISED_COLS = ["cpu_utilization", "bandwidth_mbps"]
REQUIRED_COLS = ["cpu_utilization", "bandwidth_mbps", "congestion_flag"]
MIN_ROW_COUNT = 100


def _load_df():
    if not os.path.exists(PROCESSED_PATH):
        pytest.skip(f"Processed file not found at '{PROCESSED_PATH}'. Run 'make data' first.")
    return pd.read_csv(PROCESSED_PATH)


class TestProcessed6GCSV:
    """Data tests for the processed 6G dataset."""

    def test_no_null_values(self):
        """The processed CSV must not contain any null values."""
        df = _load_df()
        null_counts = df[REQUIRED_COLS].isnull().sum()
        assert null_counts.sum() == 0, f"Null values found:\n{null_counts[null_counts > 0]}"

    def test_correct_column_count(self):
        """The processed CSV must have exactly three columns."""
        df = _load_df()
        assert len(df.columns) == len(
            REQUIRED_COLS
        ), f"Expected {len(REQUIRED_COLS)} columns, got {len(df.columns)}: {list(df.columns)}"

    def test_required_columns_present(self):
        """All required column names must be present."""
        df = _load_df()
        for col in REQUIRED_COLS:
            assert col in df.columns, f"Missing column: '{col}'"

    def test_normalised_columns_in_range(self):
        """Normalised columns must lie within [0, 1]."""
        df = _load_df()
        for col in NORMALISED_COLS:
            col_min = df[col].min()
            col_max = df[col].max()
            assert col_min >= 0.0, f"'{col}' min {col_min:.4f} < 0"
            assert col_max <= 1.0, f"'{col}' max {col_max:.4f} > 1"

    def test_row_count_exceeds_minimum(self):
        """The processed dataset must contain more than 100 rows."""
        df = _load_df()
        assert len(df) > MIN_ROW_COUNT, f"Row count {len(df)} does not exceed minimum {MIN_ROW_COUNT}."
