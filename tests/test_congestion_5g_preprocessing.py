"""Unit tests for the 5G Congestion preprocessing logic."""

import pandas as pd
import numpy as np

from src.data.preprocess_congestion_5g import slice_wise_temporal_split, CongestionPreprocessor, SEQ_LENGTH


def test_slice_wise_temporal_split():
    """Ensure the split maintains temporal order and stratifies slices properly."""
    df = pd.DataFrame({
        "slice_id": ["A"] * 10 + ["B"] * 10,
        "timestamp": pd.date_range("2023-01-01", periods=20, freq="h"),
        "congestion_flag": np.random.randint(0, 2, size=(20,))
    })
    
    train, val, test = slice_wise_temporal_split(df, train_ratio=0.6, val_ratio=0.2)
    
    assert len(train) == 12  # 6 from A, 6 from B
    assert len(val) == 4
    assert len(test) == 4
    
    assert "A" in train["slice_id"].values and "B" in train["slice_id"].values


def test_preprocessor_sequences():
    """Ensure preprocessor constructs the sliding window correctly."""
    df = pd.DataFrame({
        "slice_id": ["A"] * 50,
        "slice_type": ["eMBB"] * 50,
        "timestamp": pd.date_range("2023-01-01", periods=50, freq="h"),
        "cpu_util_pct": np.random.rand(50),
        "mem_util_pct": np.random.rand(50),
        "bw_util_pct": np.random.rand(50),
        "active_users": np.random.randint(10, 100, 50),
        "queue_len": np.random.randint(0, 10, 50),
        "congestion_flag": np.random.randint(0, 2, 50)
    })
    
    prep = CongestionPreprocessor(seq_length=5) # use 5 to make it easier to test
    prep.fit(df)
    features_scaled, target = prep.transform(df)
    X, y, slice_ids = prep.create_sequences_by_slice(df, features_scaled, target)
    
    # 50 rows per slice. 50 - 5 = 45 sequences
    assert X.shape == (45, 5, 7)
    assert y.shape == (45,)
