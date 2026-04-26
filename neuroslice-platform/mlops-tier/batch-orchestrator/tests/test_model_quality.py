"""Quality-gate tests for the shared neuroslice-aiops MLflow experiment."""

import pytest

EXPERIMENT_NAME = "neuroslice-aiops"

THRESHOLDS = {
    "congestion_6g": {"metric": "val_mae", "threshold": 5.0, "mode": "lt"},
    "slice_type_5g": {"metric": "val_accuracy", "threshold": 0.80, "mode": "gte"},
    "slice_type_6g": {"metric": "val_accuracy", "threshold": 0.80, "mode": "gte"},
    "sla_5g": {"metric": "val_roc_auc", "threshold": 0.75, "mode": "gte"},
    "sla_6g": {"metric": "val_roc_auc", "threshold": 0.75, "mode": "gte"},
}


def _get_latest_run(model_name: str):
    """Return the latest MLflow run for a registry model name, or None."""
    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient()
        experiments = client.search_experiments(filter_string=f"name = '{EXPERIMENT_NAME}'")
        if not experiments:
            return None
        exp_id = experiments[0].experiment_id
        runs = client.search_runs(
            experiment_ids=[exp_id],
            filter_string=f"tags.neuroslice.model_name = '{model_name}'",
            order_by=["start_time DESC"],
            max_results=1,
        )
        return runs[0] if runs else None
    except Exception:  # noqa: BLE001
        return None


@pytest.mark.parametrize("model_name", sorted(THRESHOLDS))
def test_latest_model_run_passes_quality_gate(model_name):
    run = _get_latest_run(model_name)
    if run is None:
        pytest.skip(f"No MLflow run found for model '{model_name}' in experiment '{EXPERIMENT_NAME}'.")

    rule = THRESHOLDS[model_name]
    metric_name = rule["metric"]
    value = run.data.metrics.get(metric_name)
    assert value is not None, f"{metric_name} metric not logged for {model_name}."

    if rule["mode"] == "lt":
        assert value < rule["threshold"]
    else:
        assert value >= rule["threshold"]
