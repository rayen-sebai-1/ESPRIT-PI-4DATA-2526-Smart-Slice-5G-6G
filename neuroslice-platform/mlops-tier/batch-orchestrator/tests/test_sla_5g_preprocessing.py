"""Unit tests for src/data/preprocess_sla.py."""

import io

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_sla_csv(rows: int = 500) -> io.StringIO:
    """Return a minimal in-memory CSV that mimics the 5G_prepared dataset."""
    rng = np.random.default_rng(42)

    # Simulate the columns needed by the SLA preprocessing
    data = {
        "LTE/5g Category": rng.integers(1, 20, rows),
        "Time": rng.integers(0, 24, rows),
        "Packet Loss Rate": rng.choice([0.000001, 0.001, 0.005, 0.01], rows),
        "Packet delay": rng.choice([10, 50, 100, 300], rows),
        "IoT": rng.integers(0, 2, rows),
        "LTE/5G": rng.integers(0, 2, rows),
        "GBR": rng.integers(0, 2, rows),
        "Non-GBR": rng.integers(0, 2, rows),
        "AR/VR/Gaming": rng.integers(0, 2, rows),
        "Healthcare": rng.integers(0, 2, rows),
        "Industry 4.0": rng.integers(0, 2, rows),
        "IoT Devices": rng.integers(0, 2, rows),
        "Public Safety": rng.integers(0, 2, rows),
        "Smart City & Home": rng.integers(0, 2, rows),
        "Smart Transportation": rng.integers(0, 2, rows),
        "Smartphone": rng.integers(0, 2, rows),
        "slice Type": rng.choice([1, 2, 3], rows),
        "service_intensity": rng.integers(0, 4, rows),
        "delay_risk": rng.uniform(0, 1, rows),
        "loss_risk": rng.uniform(0, 1, rows),
        "risk_score": rng.uniform(0, 1, rows),
        "sla_met": rng.choice([0, 0, 0, 1], rows),  # imbalanced
    }
    df = pd.DataFrame(data)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestPreprocessSLA:
    """Tests for the SLA preprocessing pipeline."""

    def test_preprocess_returns_correct_keys(self, tmp_path, monkeypatch):
        """preprocess() should return a dict with expected keys."""
        import src.data.preprocess_sla_5g as module

        # Write temp raw CSV
        raw_file = tmp_path / "5G_prepared.csv"
        buf = _make_sla_csv(500)
        raw_file.write_text(buf.read())

        proc_dir = tmp_path / "processed"
        proc_dir.mkdir()

        monkeypatch.setattr(module, "RAW_PATH", str(raw_file))
        monkeypatch.setattr(module, "PROCESSED_NPZ", str(proc_dir / "sla_5g_processed.npz"))
        monkeypatch.setattr(module, "SCALER_PATH", str(proc_dir / "scaler_sla_5g.pkl"))
        monkeypatch.setattr(module, "PROCESSED_DIR", str(proc_dir))

        result = module.preprocess()

        assert "X_train" in result
        assert "y_train" in result
        assert "X_test" in result
        assert "y_test" in result
        assert "feature_names" in result

    def test_feature_count(self, tmp_path, monkeypatch):
        """Preprocessed data must have exactly 5 features."""
        import src.data.preprocess_sla_5g as module

        raw_file = tmp_path / "5G_prepared.csv"
        buf = _make_sla_csv(500)
        raw_file.write_text(buf.read())

        proc_dir = tmp_path / "processed"
        proc_dir.mkdir()

        monkeypatch.setattr(module, "RAW_PATH", str(raw_file))
        monkeypatch.setattr(module, "PROCESSED_NPZ", str(proc_dir / "sla_5g_processed.npz"))
        monkeypatch.setattr(module, "SCALER_PATH", str(proc_dir / "scaler_sla_5g.pkl"))
        monkeypatch.setattr(module, "PROCESSED_DIR", str(proc_dir))

        result = module.preprocess()

        assert result["X_train"].shape[1] == 5
        assert result["X_test"].shape[1] == 5
        assert len(result["feature_names"]) == 5

    def test_smote_balances_classes(self, tmp_path, monkeypatch):
        """After SMOTE, both classes should have equal counts in train set."""
        import src.data.preprocess_sla_5g as module

        raw_file = tmp_path / "5G_prepared.csv"
        buf = _make_sla_csv(1000)
        raw_file.write_text(buf.read())

        proc_dir = tmp_path / "processed"
        proc_dir.mkdir()

        monkeypatch.setattr(module, "RAW_PATH", str(raw_file))
        monkeypatch.setattr(module, "PROCESSED_NPZ", str(proc_dir / "sla_5g_processed.npz"))
        monkeypatch.setattr(module, "SCALER_PATH", str(proc_dir / "scaler_sla_5g.pkl"))
        monkeypatch.setattr(module, "PROCESSED_DIR", str(proc_dir))

        result = module.preprocess()

        unique, counts = np.unique(result["y_train"], return_counts=True)
        class_counts = dict(zip(unique, counts))

        # SMOTE should make both classes equal
        assert len(class_counts) == 2, f"Expected 2 classes, got {len(class_counts)}"
        assert class_counts[0] == class_counts[1], f"Classes not balanced: {class_counts}"

    def test_no_nan_in_output(self, tmp_path, monkeypatch):
        """Preprocessed arrays should contain no NaN values."""
        import src.data.preprocess_sla_5g as module

        raw_file = tmp_path / "5G_prepared.csv"
        buf = _make_sla_csv(500)
        raw_file.write_text(buf.read())

        proc_dir = tmp_path / "processed"
        proc_dir.mkdir()

        monkeypatch.setattr(module, "RAW_PATH", str(raw_file))
        monkeypatch.setattr(module, "PROCESSED_NPZ", str(proc_dir / "sla_5g_processed.npz"))
        monkeypatch.setattr(module, "SCALER_PATH", str(proc_dir / "scaler_sla_5g.pkl"))
        monkeypatch.setattr(module, "PROCESSED_DIR", str(proc_dir))

        result = module.preprocess()

        assert not np.isnan(result["X_train"]).any()
        assert not np.isnan(result["X_test"]).any()
        assert not np.isnan(result["y_train"]).any()
        assert not np.isnan(result["y_test"]).any()

    def test_saves_files(self, tmp_path, monkeypatch):
        """preprocess() should create the .npz and .pkl files."""
        import src.data.preprocess_sla_5g as module

        raw_file = tmp_path / "5G_prepared.csv"
        buf = _make_sla_csv(500)
        raw_file.write_text(buf.read())

        proc_dir = tmp_path / "processed"
        proc_dir.mkdir()

        npz_path = str(proc_dir / "sla_5g_processed.npz")
        pkl_path = str(proc_dir / "scaler_sla_5g.pkl")

        monkeypatch.setattr(module, "RAW_PATH", str(raw_file))
        monkeypatch.setattr(module, "PROCESSED_NPZ", npz_path)
        monkeypatch.setattr(module, "SCALER_PATH", pkl_path)
        monkeypatch.setattr(module, "PROCESSED_DIR", str(proc_dir))

        module.preprocess()

        import os

        assert os.path.exists(npz_path), "NPZ file not created"
        assert os.path.exists(pkl_path), "Scaler PKL file not created"
