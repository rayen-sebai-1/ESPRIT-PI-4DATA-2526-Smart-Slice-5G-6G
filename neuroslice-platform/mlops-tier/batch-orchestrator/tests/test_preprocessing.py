"""Unit tests for src/data/preprocess_6g.py."""

import io

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_csv(rows: int = 200) -> io.StringIO:
    """Return a minimal in-memory CSV that mimics the enriched dataset."""
    rng = np.random.default_rng(42)
    data = {
        "cpu_util_pct": rng.uniform(30, 100, rows),
        "bw_util_pct": rng.uniform(20, 100, rows),
        "congestion_flag": rng.integers(0, 2, rows),
    }
    df = pd.DataFrame(data)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestPreprocess6G:
    """Tests for the 6G preprocessing pipeline."""

    def test_load_returns_dataframe_with_correct_columns(self, tmp_path, monkeypatch):
        """preprocess() should return a DataFrame with the three required columns."""
        import src.data.preprocess_6g as module

        # Write a temporary raw CSV (mimics network_slicing_dataset_enriched_timeseries.csv)
        raw_file = tmp_path / "network_slicing_dataset_enriched_timeseries.csv"
        buf = _make_csv(300)
        raw_file.write_text(buf.read())

        proc_dir = tmp_path / "processed"
        proc_dir.mkdir()

        # Patch constants so we use the temp paths
        monkeypatch.setattr(module, "RAW_PATH", str(raw_file))
        monkeypatch.setattr(
            module, "PROCESSED_PATH", str(proc_dir / "6g_processed.csv")
        )

        df = module.preprocess()

        assert isinstance(df, pd.DataFrame)
        assert set(df.columns) == {
            "cpu_utilization",
            "bandwidth_mbps",
            "congestion_flag",
        }

    def test_normalised_columns_in_range(self, tmp_path, monkeypatch):
        """After preprocessing the normalised columns must lie within [0, 1]."""
        import src.data.preprocess_6g as module

        raw_file = tmp_path / "network_slicing_dataset_enriched_timeseries.csv"
        buf = _make_csv(300)
        raw_file.write_text(buf.read())

        proc_dir = tmp_path / "processed"
        proc_dir.mkdir()

        monkeypatch.setattr(module, "RAW_PATH", str(raw_file))
        monkeypatch.setattr(
            module, "PROCESSED_PATH", str(proc_dir / "6g_processed.csv")
        )

        df = module.preprocess()

        assert df["cpu_utilization"].min() >= 0.0
        assert df["cpu_utilization"].max() <= 1.0
        assert df["bandwidth_mbps"].min() >= 0.0
        assert df["bandwidth_mbps"].max() <= 1.0


class TestBuildSequences:
    """Tests for the sequence-creation helper."""

    def test_sequence_shape(self):
        """build_sequences should return arrays with shape (N, 24, 2) and (N,)."""
        from src.models.train_congestion_6g import build_sequences

        rows = 200
        rng = np.random.default_rng(0)
        df = pd.DataFrame(
            {
                "cpu_utilization": rng.random(rows),
                "bandwidth_mbps": rng.random(rows),
                "congestion_flag": rng.integers(0, 2, rows),
            }
        )

        X, y = build_sequences(df, seq_length=24)

        expected_n = rows - 24
        assert X.shape == (expected_n, 24, 2), f"Got {X.shape}"
        assert y.shape == (expected_n,), f"Got {y.shape}"

    def test_scaler_output_in_range(self):
        """After MinMaxScaling the normalised values should be in [0, 1]."""
        from sklearn.preprocessing import MinMaxScaler

        rng = np.random.default_rng(1)
        raw = rng.uniform(30, 100, (100, 2))
        scaled = MinMaxScaler().fit_transform(raw)

        assert scaled.min() >= 0.0
        assert scaled.max() <= 1.0
