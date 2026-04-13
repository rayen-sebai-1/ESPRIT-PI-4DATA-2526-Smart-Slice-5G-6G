"""Preprocessing script for the Congestion 5G LSTM model.

Loads raw train_dataset_enriched_timeseries.csv, selects final features,
extracts hour, applies LabelEncoder, and StandardScaling.
Splits train/val/test slice-wise with temporal splits (60/20/20) and 
sequences the data (seq_length=30).

Outputs:
    data/processed/congestion_5g_processed.npz  — sequence arrays + metadata
    data/processed/preprocessor_congestion_5g.pkl — fitted scalers/encoders
"""

import os
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RAW_PATH = "data/raw/train_dataset_enriched_timeseries.csv"
PROCESSED_DIR = "data/processed"
PROCESSED_NPZ = os.path.join(PROCESSED_DIR, "congestion_5g_processed.npz")
PREPROCESSOR_PATH = os.path.join(PROCESSED_DIR, "preprocessor_congestion_5g.pkl")

SEQ_LENGTH = 30
TARGET = "congestion_flag"

def slice_wise_temporal_split(df, train_ratio=0.6, val_ratio=0.2):
    """Split data by slice_id, maintaining temporal order within each slice."""
    train_dfs, val_dfs, test_dfs = [], [], []

    for slice_id in df['slice_id'].unique():
        slice_df = df[df['slice_id'] == slice_id].sort_values('timestamp')
        n = len(slice_df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_dfs.append(slice_df.iloc[:train_end])
        val_dfs.append(slice_df.iloc[train_end:val_end])
        test_dfs.append(slice_df.iloc[val_end:])

    return pd.concat(train_dfs), pd.concat(val_dfs), pd.concat(test_dfs)

class CongestionPreprocessor:
    """Preprocesses raw frames into scaled sequences."""
    def __init__(self, seq_length=30):
        self.seq_length = seq_length
        self.scaler = StandardScaler()
        self.le = LabelEncoder()
        self.feature_cols = [
            'cpu_util_pct', 'mem_util_pct', 'bw_util_pct',
            'active_users', 'queue_len', 'hour', 'slice_type_encoded'
        ]

    def fit(self, df):
        # Fit LabelEncoder on the entire dataset first!
        self.le.fit(df['slice_type'])
        
        # We need a temporary copy to fit the scaler
        df_temp = df.copy()
        df_temp['slice_type_encoded'] = self.le.transform(df_temp['slice_type'])
        df_temp['hour'] = pd.to_datetime(df_temp['timestamp']).dt.hour
        self.scaler.fit(df_temp[self.feature_cols].values)
        return self

    def transform(self, df):
        df_temp = df.copy()
        df_temp['slice_type_encoded'] = self.le.transform(df_temp['slice_type'])
        df_temp['hour'] = pd.to_datetime(df_temp['timestamp']).dt.hour
        features_scaled = self.scaler.transform(df_temp[self.feature_cols].values)
        return features_scaled, df_temp[TARGET].values

    def create_sequences_by_slice(self, df, features, target):
        X, y, slice_ids = [], [], []

        for slice_id in df['slice_id'].unique():
            slice_mask = df['slice_id'].values == slice_id
            slice_features = features[slice_mask]
            slice_target = target[slice_mask]

            for i in range(len(slice_features) - self.seq_length):
                X.append(slice_features[i:i+self.seq_length])
                y.append(slice_target[i+self.seq_length])
                slice_ids.append(slice_id)

        return np.array(X), np.array(y), np.array(slice_ids)


def preprocess() -> dict:
    global RAW_PATH
    if not os.path.exists(RAW_PATH):
        # Maybe it's not in raw folder in this repo structure, check notebooks path or root
        alt_paths = ["train_dataset_enriched_timeseries.csv", 
                     "data/train_dataset_enriched_timeseries.csv",
                     "notebooks/train_dataset_enriched_timeseries.csv"]
        found = False
        for alt in alt_paths:
            if os.path.exists(alt):
                RAW_PATH = alt
                found = True
                break
        if not found:
            raise FileNotFoundError(f"Raw data not found. Please ensure 'train_dataset_enriched_timeseries.csv' exists.")

    df = pd.read_csv(RAW_PATH)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(f"[INFO] Loaded {df.shape[0]} rows from '{RAW_PATH}'.")

    # Fit preprocessor
    preprocessor = CongestionPreprocessor(seq_length=SEQ_LENGTH)
    preprocessor.fit(df)  # Fit LE on all, scaler on all initially or just train? The notebook fits LE on all, and scaler on train!
    # Wait, in the notebook, scaler is fit on df_train. Let's fix that.
    preprocessor.le.fit(df['slice_type'])
    df['slice_type_encoded'] = preprocessor.le.transform(df['slice_type'])
    df['hour'] = df['timestamp'].dt.hour
    
    # Split Data
    df_train, df_val, df_test = slice_wise_temporal_split(df, train_ratio=0.6, val_ratio=0.2)
    print(f"[INFO] Train: {len(df_train)} | Val: {len(df_val)} | Test: {len(df_test)}")

    # Fit scaler on train only
    preprocessor.scaler.fit(df_train[preprocessor.feature_cols].values)

    # Transform
    X_train_raw, y_train_raw = preprocessor.transform(df_train)
    X_val_raw, y_val_raw = preprocessor.transform(df_val)
    X_test_raw, y_test_raw = preprocessor.transform(df_test)

    # Sequences
    X_train, y_train, _ = preprocessor.create_sequences_by_slice(df_train, X_train_raw, y_train_raw)
    X_val, y_val, _ = preprocessor.create_sequences_by_slice(df_val, X_val_raw, y_val_raw)
    X_test, y_test, _ = preprocessor.create_sequences_by_slice(df_test, X_test_raw, y_test_raw)

    print(f"[INFO] Sequences -> Train: {X_train.shape} | Val: {X_val.shape} | Test: {X_test.shape}")

    # Save
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    np.savez(
        PROCESSED_NPZ,
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test,
        feature_names=np.array(preprocessor.feature_cols),
    )
    print(f"[INFO] Saved processed data to '{PROCESSED_NPZ}'.")

    joblib.dump(preprocessor, PREPROCESSOR_PATH)
    print(f"[INFO] Saved preprocessor to '{PREPROCESSOR_PATH}'.")

    return {
        "X_train": X_train,
        "X_val": X_val,
        "X_test": X_test,
        "y_train": y_train,
        "feature_names": preprocessor.feature_cols,
    }


if __name__ == "__main__":
    preprocess()
