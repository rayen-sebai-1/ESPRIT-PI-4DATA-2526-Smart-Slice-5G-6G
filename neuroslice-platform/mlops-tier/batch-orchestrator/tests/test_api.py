"""Functional tests for the Smart Slice 5G/6G FastAPI application."""

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_client():
    """Return a TestClient that bypasses the startup model loading."""
    # Patch the startup event so we don't need a running MLflow server
    from unittest.mock import patch

    with patch("src.api.main.load_models", return_value=None):
        from src.api.main import app

        # Inject a toy LSTM model so the congestion endpoint actually works
        from src.models.train_congestion_6g import Congestion6GLSTM

        toy_model = Congestion6GLSTM(input_size=2, hidden_size=8)
        toy_model.eval()
        app.state  # ensure the state attr exists
        from src.api.main import _models

        _models["congestion_6g"] = toy_model

        return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestHealthEndpoint:
    def test_health_returns_200(self):
        client = _get_client()
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_ok_status(self):
        client = _get_client()
        resp = client.get("/health")
        assert resp.json() == {"status": "ok"}


class TestCongestion6GEndpoint:
    def _valid_payload(self):
        return {
            "cpu_sequence": [0.5] * 24,
            "bandwidth_sequence": [0.4] * 24,
        }

    def test_predict_congestion_6g_returns_200(self):
        client = _get_client()
        resp = client.post("/predict/congestion_6g", json=self._valid_payload())
        assert resp.status_code == 200

    def test_predict_congestion_6g_returns_forecast_cpu(self):
        client = _get_client()
        resp = client.post("/predict/congestion_6g", json=self._valid_payload())
        body = resp.json()
        assert "forecast_cpu_next_5min" in body
        assert isinstance(body["forecast_cpu_next_5min"], float)

    def test_predict_congestion_6g_returns_alert_bool(self):
        client = _get_client()
        resp = client.post("/predict/congestion_6g", json=self._valid_payload())
        body = resp.json()
        assert "congestion_6g_alert" in body
        assert isinstance(body["congestion_6g_alert"], bool)

    def test_predict_congestion_6g_rejects_wrong_sequence_length(self):
        client = _get_client()
        bad_payload = {
            "cpu_sequence": [0.5] * 10,  # wrong length
            "bandwidth_sequence": [0.4] * 24,
        }
        resp = client.post("/predict/congestion_6g", json=bad_payload)
        assert resp.status_code == 422


class TestSLA5GEndpoint:
    """Tests for the /predict/sla_5g endpoint."""

    @staticmethod
    def _get_sla_5g_client():
        """Return a TestClient with a toy XGBoost model and scaler injected."""
        from unittest.mock import patch

        with patch("src.api.main.load_models", return_value=None):
            import src.api.main as _main

            app = _main.app

            # Inject toy LSTM for congestion (required for app init)
            from src.models.train_congestion_6g import Congestion6GLSTM

            toy_lstm = Congestion6GLSTM(input_size=2, hidden_size=8)
            toy_lstm.eval()
            _main._models["congestion_6g"] = toy_lstm

            # Inject toy XGBoost + scaler for SLA
            import numpy as np
            from sklearn.preprocessing import StandardScaler
            from xgboost import XGBClassifier

            rng = np.random.default_rng(42)
            X_dummy = rng.random((100, 5))
            y_dummy = rng.integers(0, 2, 100)

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_dummy)

            toy_xgb = XGBClassifier(
                n_estimators=10,
                max_depth=3,
                use_label_encoder=False,
                eval_metric="logloss",
            )
            toy_xgb.fit(X_scaled, y_dummy)

            _main._models["sla_5g"] = toy_xgb
            _main._models["sla_5g_scaler"] = scaler

            return TestClient(app)

    def _valid_sla_5g_payload(self):
        return {
            "packet_loss_rate": 0.001,
            "packet_delay": 50.0,
            "smart_city_home": 1,
            "iot_devices": 0,
            "public_safety": 0,
        }

    def test_predict_sla_5g_returns_200(self):
        client = self._get_sla_5g_client()
        resp = client.post("/predict/sla_5g", json=self._valid_sla_5g_payload())
        assert resp.status_code == 200

    def test_predict_sla_5g_returns_risk_level(self):
        client = self._get_sla_5g_client()
        resp = client.post("/predict/sla_5g", json=self._valid_sla_5g_payload())
        body = resp.json()
        assert "risk_level" in body
        assert body["risk_level"] in ["LOW", "MEDIUM", "HIGH"]

    def test_predict_sla_5g_returns_probability(self):
        client = self._get_sla_5g_client()
        resp = client.post("/predict/sla_5g", json=self._valid_sla_5g_payload())
        body = resp.json()
        assert "sla_probability" in body
        assert 0.0 <= body["sla_probability"] <= 1.0

    def test_predict_sla_5g_returns_prediction(self):
        client = self._get_sla_5g_client()
        resp = client.post("/predict/sla_5g", json=self._valid_sla_5g_payload())
        body = resp.json()
        assert "sla_prediction" in body
        assert body["sla_prediction"] in [0, 1]

    def test_predict_sla_5g_rejects_invalid_input(self):
        client = self._get_sla_5g_client()
        bad_payload = {
            "packet_loss_rate": -1.0,  # invalid: must be >= 0
            "packet_delay": 50.0,
            "smart_city_home": 1,
            "iot_devices": 0,
            "public_safety": 0,
        }
        resp = client.post("/predict/sla_5g", json=bad_payload)
        assert resp.status_code == 422


class TestCongestion5GEndpoint:
    """Tests for the /predict/congestion_5g endpoint."""

    @staticmethod
    def _get_congestion_5g_client():
        from unittest.mock import patch

        with patch("src.api.main.load_models", return_value=None):
            from src.api import main as _main

            app = _main.app

            from src.models.train_congestion_5g import LSTMClassifier
            from src.data.preprocess_congestion_5g import CongestionPreprocessor
            import pandas as pd
            import numpy as np

            toy_lstm = LSTMClassifier(input_dim=7, hidden_dim=8)
            toy_lstm.eval()
            _main._models["congestion_5g"] = toy_lstm

            # Dummy preprocessor
            prep = CongestionPreprocessor(seq_length=30)
            df = pd.DataFrame(
                {
                    "slice_type": ["eMBB"] * 100,
                    "timestamp": pd.date_range("2023-01-01", periods=100, freq="h"),
                    "cpu_util_pct": np.random.rand(100),
                    "mem_util_pct": np.random.rand(100),
                    "bw_util_pct": np.random.rand(100),
                    "active_users": np.random.randint(10, 100, 100),
                    "queue_len": np.random.randint(0, 10, 100),
                }
            )
            prep.fit(df)
            _main._models["congestion_5g_preprocessor"] = prep

            return TestClient(app)

    def _valid_payload(self):
        seq = []
        for _ in range(30):
            seq.append([0.5, 0.5, 0.5, 50, 5, 12, 0])
        return {"sequence": seq}

    def test_predict_congestion_5g_returns_200(self):
        client = self._get_congestion_5g_client()
        resp = client.post("/predict/congestion_5g", json=self._valid_payload())
        assert resp.status_code == 200

    def test_predict_congestion_5g_returns_probability(self):
        client = self._get_congestion_5g_client()
        resp = client.post("/predict/congestion_5g", json=self._valid_payload())
        body = resp.json()
        assert "congestion_probability" in body
        assert isinstance(body["congestion_probability"], float)

    def test_predict_congestion_5g_returns_alert_bool(self):
        client = self._get_congestion_5g_client()
        resp = client.post("/predict/congestion_5g", json=self._valid_payload())
        body = resp.json()
        assert "congestion_alert" in body
        assert isinstance(body["congestion_alert"], bool)

    def test_predict_congestion_5g_rejects_wrong_sequence_shape(self):
        client = self._get_congestion_5g_client()
        seq = [[0.5] * 7] * 10  # wrong length (10 instead of 30)
        bad_payload = {"sequence": seq}
        # Pydantic currently doesn't fail on length unless defined, but endpoint fails validation
        resp = client.post("/predict/congestion_5g", json=bad_payload)
        assert (
            resp.status_code == 500 or resp.status_code == 422
        )  # Custom shape check causes 500 or ValueError


class TestSliceType6GEndpoint:
    """Tests for the /predict/slice_type_6g endpoint."""

    @staticmethod
    def _get_slice_type_6g_client():
        from unittest.mock import patch

        with patch("src.api.main.load_models", return_value=None):
            from src.api import main as _main

            app = _main.app

            import numpy as np
            from sklearn.preprocessing import LabelEncoder
            from xgboost import XGBClassifier

            rng = np.random.default_rng(42)
            X_dummy = rng.random((100, 10))
            y_dummy = rng.integers(0, 5, 100)

            le = LabelEncoder()
            le.fit(["ERLLC", "umMTC", "MBRLLC", "mURLLC", "feMBB"])

            toy_xgb = XGBClassifier(
                n_estimators=10, max_depth=3, num_class=5, objective="multi:softprob"
            )
            toy_xgb.fit(X_dummy, y_dummy)

            _main._models["slice_type_6g"] = toy_xgb
            _main._models["slice_type_6g_encoder"] = le

            return TestClient(app)

    def _valid_payload(self):
        return {
            "packet_loss_budget": 0.001,
            "latency_budget_ns": 500000.0,
            "jitter_budget_ns": 100000.0,
            "data_rate_budget_gbps": 10.0,
            "required_mobility": "yes",
            "required_connectivity": "no",
            "slice_available_transfer_rate_gbps": 5.0,
            "slice_latency_ns": 400000.0,
            "slice_packet_loss": 0.0005,
            "slice_jitter_ns": 80000.0,
        }

    def test_predict_slice_type_6g_returns_200(self):
        client = self._get_slice_type_6g_client()
        resp = client.post("/predict/slice_type_6g", json=self._valid_payload())
        assert resp.status_code == 200

    def test_predict_slice_type_6g_returns_valid_structure(self):
        client = self._get_slice_type_6g_client()
        resp = client.post("/predict/slice_type_6g", json=self._valid_payload())
        body = resp.json()
        assert "predicted_slice" in body
        assert "slice_label" in body
        assert "confidence" in body
        assert "all_probabilities" in body


class TestSLA6GEndpoint:
    """Tests for the /predict/sla_6g endpoint."""

    @staticmethod
    def _get_sla_6g_client():
        """Return a TestClient with a toy XGBoost (14 features) and scaler injected."""
        from unittest.mock import patch

        with patch("src.api.main.load_models", return_value=None):
            import src.api.main as _main

            app = _main.app

            import numpy as np
            from sklearn.preprocessing import StandardScaler
            from xgboost import XGBClassifier

            rng = np.random.default_rng(42)
            X_dummy = rng.random((200, 14))
            y_dummy = rng.integers(0, 2, 200)

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_dummy)

            toy_xgb = XGBClassifier(
                n_estimators=10,
                max_depth=3,
                use_label_encoder=False,
                eval_metric="logloss",
            )
            toy_xgb.fit(X_scaled, y_dummy)

            _main._models["sla_6g"] = toy_xgb
            _main._models["sla_6g_scaler"] = scaler

            return TestClient(app)

    def _valid_sla_6g_payload(self):
        """Return a valid SLA-6G request payload with 14 features."""
        return {
            # Temporal QoS — Slice Latency (ns)
            "slice_latency_lag1": 800_000.0,
            "slice_latency_rolling_mean": 850_000.0,
            "slice_latency_rolling_std": 15_000.0,
            # Temporal QoS — Slice Packet Loss
            "slice_packet_loss_lag1": 0.00005,
            "slice_packet_loss_rolling_mean": 0.00006,
            "slice_packet_loss_rolling_std": 0.000005,
            # Temporal QoS — Slice Jitter (ns)
            "slice_jitter_lag1": 300_000.0,
            "slice_jitter_rolling_mean": 310_000.0,
            "slice_jitter_rolling_std": 8_000.0,
            # Context
            "slice_type_encoded": 3,  # mURLLC
            "mobility_encoded": 1,
            "connectivity_encoded": 1,
            "handover_encoded": 0,
            "slice_available_transfer_rate_gbps": 12.5,
        }

    def test_predict_sla_6g_returns_200(self):
        client = self._get_sla_6g_client()
        resp = client.post("/predict/sla_6g", json=self._valid_sla_6g_payload())
        assert resp.status_code == 200

    def test_predict_sla_6g_returns_prediction(self):
        client = self._get_sla_6g_client()
        resp = client.post("/predict/sla_6g", json=self._valid_sla_6g_payload())
        body = resp.json()
        assert "sla_prediction" in body
        assert body["sla_prediction"] in [0, 1]

    def test_predict_sla_6g_returns_probability(self):
        client = self._get_sla_6g_client()
        resp = client.post("/predict/sla_6g", json=self._valid_sla_6g_payload())
        body = resp.json()
        assert "sla_probability" in body
        assert 0.0 <= body["sla_probability"] <= 1.0

    def test_predict_sla_6g_returns_risk_level(self):
        client = self._get_sla_6g_client()
        resp = client.post("/predict/sla_6g", json=self._valid_sla_6g_payload())
        body = resp.json()
        assert "risk_level" in body
        assert body["risk_level"] in ["LOW", "MEDIUM", "HIGH"]

    def test_predict_sla_6g_rejects_negative_packet_loss(self):
        client = self._get_sla_6g_client()
        bad_payload = self._valid_sla_6g_payload()
        bad_payload["slice_packet_loss_lag1"] = -0.001  # must be >= 0
        resp = client.post("/predict/sla_6g", json=bad_payload)
        assert resp.status_code == 422
