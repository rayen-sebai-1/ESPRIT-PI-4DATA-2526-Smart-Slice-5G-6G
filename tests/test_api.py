"""Functional tests for the Smart Slice 5G/6G FastAPI application."""

import pytest
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
        import torch
        from src.models.train_congestion_6g import CongestionLSTM

        toy_model = CongestionLSTM(input_size=2, hidden_size=8)
        toy_model.eval()
        app.state  # ensure the state attr exists
        from src.api import main as _main

        _main._models["congestion"] = toy_model

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


class TestCongestionEndpoint:
    def _valid_payload(self):
        return {
            "cpu_sequence": [0.5] * 24,
            "bandwidth_sequence": [0.4] * 24,
        }

    def test_predict_congestion_returns_200(self):
        client = _get_client()
        resp = client.post("/predict/congestion", json=self._valid_payload())
        assert resp.status_code == 200

    def test_predict_congestion_returns_forecast_cpu(self):
        client = _get_client()
        resp = client.post("/predict/congestion", json=self._valid_payload())
        body = resp.json()
        assert "forecast_cpu_next_5min" in body
        assert isinstance(body["forecast_cpu_next_5min"], float)

    def test_predict_congestion_returns_alert_bool(self):
        client = _get_client()
        resp = client.post("/predict/congestion", json=self._valid_payload())
        body = resp.json()
        assert "congestion_alert" in body
        assert isinstance(body["congestion_alert"], bool)

    def test_predict_congestion_rejects_wrong_sequence_length(self):
        client = _get_client()
        bad_payload = {
            "cpu_sequence": [0.5] * 10,  # wrong length
            "bandwidth_sequence": [0.4] * 24,
        }
        resp = client.post("/predict/congestion", json=bad_payload)
        assert resp.status_code == 422
