"""Preprocessing script for the 6G network slicing dataset.

Loads raw 6G CSV, cleans missing values, normalizes CPU and bandwidth columns
using MinMaxScaler, creates time-series sequences of length 24 for the LSTM
input, and saves the processed output to data/processed/6g_processed.csv.
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

RAW_PATH = "data/raw/network_slicing_dataset_enriched_timeseries.csv"
LEGACY_RAW_PATH = "data/network_slicing_dataset_enriched_timeseries.csv"
PROCESSED_PATH = "data/processed/6g_processed.csv"
SEQ_LENGTH = 24

# Column names as they appear in the enriched timeseries dataset
RAW_CPU_COL = "cpu_util_pct"
RAW_BW_COL = "bw_util_pct"
RAW_TARGET_COL = "congestion_flag"
BASE_DIR = Path(__file__).resolve().parents[2]


def _resolve_path(path: str) -> Path:
    """Resolve a data path relative to the batch-orchestrator root."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return BASE_DIR / candidate


def _resolve_raw_path() -> Path:
    """Prefer canonical raw path, but support legacy in-repo location."""
    canonical = _resolve_path(RAW_PATH)
    legacy = _resolve_path(LEGACY_RAW_PATH)
    if canonical.exists():
        return canonical
    if legacy.exists():
        return legacy
    return canonical


def create_sequences(data: np.ndarray, seq_length: int = SEQ_LENGTH):
    """Create overlapping time-series sequences from a 2-D array.

    Args:
        data: Array of shape (N, features).
        seq_length: Number of time steps per sequence.

    Returns:
        Tuple (X, y) where X has shape (N-seq_length, seq_length, features)
        and y has shape (N-seq_length,).
    """
    X, y = [], []
    for i in range(len(data) - seq_length):
        X.append(data[i : i + seq_length, :2])  # noqa: E203; cpu + bandwidth features
        y.append(data[i + seq_length, 0])  # predict next cpu_utilization
    return np.array(X), np.array(y)


def preprocess() -> pd.DataFrame:
    """Run the full preprocessing pipeline.

    Returns:
        Processed DataFrame saved to PROCESSED_PATH.
    """
    # ------------------------------------------------------------------
    # 1. Load raw data
    # ------------------------------------------------------------------
    raw_path = _resolve_raw_path()
    if not os.path.exists(raw_path):
        raise FileNotFoundError(
            f"Raw data not found at '{raw_path}'. "
            "Please ensure 'network_slicing_dataset_enriched_timeseries.csv' "
            "is placed in 'data/raw/' (preferred) or 'data/' (legacy)."
        )

    df = pd.read_csv(raw_path)
    print(f"[INFO] Loaded {df.shape[0]} rows, {df.shape[1]} columns from '{raw_path}'.")

    # ------------------------------------------------------------------
    # 2. Select and rename the columns needed by the LSTM
    # ------------------------------------------------------------------
    for col in [RAW_CPU_COL, RAW_BW_COL, RAW_TARGET_COL]:
        if col not in df.columns:
            raise ValueError(
                f"Expected column '{col}' not found in the dataset. "
                f"Available columns: {list(df.columns)}"
            )

    df = df[[RAW_CPU_COL, RAW_BW_COL, RAW_TARGET_COL]].copy()
    df = df.rename(
        columns={
            RAW_CPU_COL: "cpu_utilization",
            RAW_BW_COL: "bandwidth_mbps",
            # congestion_flag keeps its name
        }
    )

    # ------------------------------------------------------------------
    # 3. Drop missing values
    # ------------------------------------------------------------------
    required_cols = ["cpu_utilization", "bandwidth_mbps", "congestion_flag"]
    before = len(df)
    df = df.dropna(subset=required_cols)
    print(f"[INFO] Dropped {before - len(df)} rows with missing values.")

    # ------------------------------------------------------------------
    # 4. Normalize CPU and bandwidth with MinMaxScaler
    # ------------------------------------------------------------------
    scaler = MinMaxScaler(feature_range=(0, 1))
    df[["cpu_utilization", "bandwidth_mbps"]] = scaler.fit_transform(
        df[["cpu_utilization", "bandwidth_mbps"]]
    )

    # ------------------------------------------------------------------
    # 5. Save processed output
    # ------------------------------------------------------------------
    df_out = df[required_cols].reset_index(drop=True)

    processed_path = _resolve_path(PROCESSED_PATH)
    os.makedirs(processed_path.parent, exist_ok=True)
    df_out.to_csv(processed_path, index=False)
    print(f"[INFO] Saved processed data to '{processed_path}' ({len(df_out)} rows).")

    return df_out


if __name__ == "__main__":
    preprocess()
