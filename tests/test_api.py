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
        from src.api import main as _main

        _main._models["congestion_6g"] = toy_model

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
            from src.api.main import app
            from src.api import main as _main

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

            toy_xgb = XGBClassifier(n_estimators=10, max_depth=3, use_label_encoder=False, eval_metric="logloss")
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
