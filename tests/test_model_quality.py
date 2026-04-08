"""Quality-gate tests: assert MLflow metrics meet minimum thresholds."""

import pytest

# Quality-gate thresholds (adjust as models are trained)
THRESHOLDS = {
    "congestion-forecast-6g": {"val_mae": 5.0},  # LSTM – primary gate
    "slice-selection-5g": {"val_accuracy": 0.80},
    "slice-selection-6g": {"val_accuracy": 0.80},
    "sla-adherence-5g": {"val_roc_auc": 0.75},
    "anomaly-detection": {"val_f1": 0.70},
}


def _get_latest_run(experiment_name: str):
    """Return the latest MLflow run for a given experiment name, or None."""
    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient()
        experiments = client.search_experiments(filter_string=f"name = '{experiment_name}'")
        if not experiments:
            return None
        exp_id = experiments[0].experiment_id
        runs = client.search_runs(
            experiment_ids=[exp_id],
            order_by=["start_time DESC"],
            max_results=1,
        )
        return runs[0] if runs else None
    except Exception:  # noqa: BLE001
        return None


class TestModelQualityGates:
    """Assert that the latest run metrics pass the minimum bar."""

    def test_congestion_6g_lstm_val_mae(self):
        """val_mae for the congestion LSTM must be < 5.0."""
        exp = "congestion-forecast-6g"
        run = _get_latest_run(exp)
        if run is None:
            pytest.skip(f"No MLflow run found for experiment '{exp}'.")
        val_mae = run.data.metrics.get("val_mae") or run.data.metrics.get("final_val_mae")
        assert val_mae is not None, "val_mae metric not logged."
        threshold = THRESHOLDS[exp]["val_mae"]
        assert val_mae < threshold, f"Quality gate failed: val_mae={val_mae:.4f} >= threshold={threshold}"

    # ------------------------------------------------------------------
    # Stub gates for models not yet trained – they will be skipped until
    # corresponding MLflow experiments exist.
    # ------------------------------------------------------------------
    def test_slice_5g_accuracy(self):
        exp = "slice-selection-5g"
        run = _get_latest_run(exp)
        if run is None:
            pytest.skip(f"No MLflow run found for experiment '{exp}'.")
        val_acc = run.data.metrics.get("val_accuracy")
        assert val_acc is not None
        assert val_acc >= THRESHOLDS[exp]["val_accuracy"]

    def test_slice_6g_accuracy(self):
        exp = "slice-selection-6g"
        run = _get_latest_run(exp)
        if run is None:
            pytest.skip(f"No MLflow run found for experiment '{exp}'.")
        val_acc = run.data.metrics.get("val_accuracy")
        assert val_acc is not None
        assert val_acc >= THRESHOLDS[exp]["val_accuracy"]

    def test_sla_roc_auc(self):
        exp = "sla-adherence-5g"
        run = _get_latest_run(exp)
        if run is None:
            pytest.skip(f"No MLflow run found for experiment '{exp}'.")
        val_auc = run.data.metrics.get("val_roc_auc")
        assert val_auc is not None
        assert val_auc >= THRESHOLDS[exp]["val_roc_auc"]

    def test_anomaly_f1(self):
        exp = "anomaly-detection"
        run = _get_latest_run(exp)
        if run is None:
            pytest.skip(f"No MLflow run found for experiment '{exp}'.")
        val_f1 = run.data.metrics.get("val_f1")
        assert val_f1 is not None
        assert val_f1 >= THRESHOLDS[exp]["val_f1"]
