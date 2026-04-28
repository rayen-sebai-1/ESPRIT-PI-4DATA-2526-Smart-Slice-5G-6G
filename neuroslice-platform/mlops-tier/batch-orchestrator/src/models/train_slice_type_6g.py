"""Training script for the Slice-Type 6G model.

Uses XGBoost to train a multiclass classifier for the 5 6G slice types.
Integrates with MLflow to track parameters, evaluation metrics, and SHAP summary plots.
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb
import mlflow
import shap

from src.models.lifecycle import configure_mlflow_tracking, finalize_model_lifecycle, get_experiment_name, use_mlflow_experiment

# Configuration
ROOT_DIR = Path(__file__).resolve().parents[2]
NPZ_PATH = ROOT_DIR / "data" / "processed" / "slice_type_6g_processed.npz"
LABEL_ENCODER_PATH = ROOT_DIR / "data" / "processed" / "label_encoder_slice_type_6g.pkl"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
LOCAL_MODEL_PATH = ROOT_DIR / "models" / "slice_type_6g_model.ubj"
MLFLOW_EXPERIMENT_NAME = get_experiment_name()
MLFLOW_TRACKING_URI = configure_mlflow_tracking()

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


def check_existing_runs():
    """Fail if an MLflow run is already active strictly."""
    if mlflow.active_run():
        mlflow.end_run()


def get_or_create_experiment(experiment_name: str) -> str:
    """Gets the experiment ID or creates a new experiment if it doesn't exist."""
    print("Finding or creating MLflow experiment...")
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(experiment_name)
        print(f"Created new experiment '{experiment_name}' with ID: {experiment_id}")
        return experiment_id
    print(f"Using existing experiment '{experiment_name}' with ID: {experiment.experiment_id}")
    return experiment.experiment_id


def main():
    print("-" * 50)
    print("Starting Slice-Type-6G Model Training (XGBoost)")
    print("-" * 50)

    # 1. Load Data
    if not NPZ_PATH.exists():
        print(f"[ERROR] Processed data not found at '{NPZ_PATH.as_posix()}'. Please run preprocessing.")
        sys.exit(1)

    print(f"Loading data from {NPZ_PATH.as_posix()}...")
    data = np.load(NPZ_PATH, allow_pickle=True)
    X_train = data["X_train"]
    y_train = data["y_train"]
    X_test = data["X_test"]
    y_test = data["y_test"]
    feature_names = data["feature_names"]

    print(f"Train samples: {X_train.shape[0]}, Test samples: {X_test.shape[0]}")

    # 2. Setup XGBoost Parameters
    params = {
        "n_estimators": 150,
        "max_depth": 6,
        "learning_rate": 0.05,
        "objective": "multi:softprob",
        "num_class": 5,
        "random_state": 42,
        "eval_metric": "mlogloss",
        "n_jobs": -1
    }

    # 3. Initialize MLflow Experiment
    check_existing_runs()
    use_mlflow_experiment(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(run_name="xgboost_multi_classifier"):
        print("Starting MLflow Run...")
        mlflow.log_params(params)

        # 4. Train Model
        print("Training XGBoost Classifier...")
        model = xgb.XGBClassifier(**params)
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

        # 5. Evaluate Model
        print("Evaluating model...")
        y_pred = model.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

        metrics = {
            "val_accuracy": acc,
            "val_precision": precision,
            "val_recall": recall,
            "val_f1_score": f1
        }
        mlflow.log_metrics(metrics)
        print("Validation Metrics:")
        for k, v in metrics.items():
            print(f"  {k}: {v:.4f}")

        # 6. SHAP Explanations
        print("Generating SHAP summary plot...")
        try:
            explainer = shap.TreeExplainer(model)
            sample_idx = np.random.choice(X_train.shape[0], min(X_train.shape[0], 2000), replace=False)
            X_train_sample = X_train[sample_idx]
            shap_values = explainer.shap_values(X_train_sample)

            plt.figure(figsize=(10, 8))
            shap.summary_plot(shap_values, X_train_sample, feature_names=feature_names, show=False)

            ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
            shap_plot_path = ARTIFACTS_DIR / "shap_summary_6g.png"
            plt.tight_layout()
            plt.savefig(shap_plot_path.as_posix(), bbox_inches="tight")
            plt.close()

            mlflow.log_artifact(shap_plot_path.as_posix())
            print(f"Logged SHAP artifact: {shap_plot_path.as_posix()}")
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] SHAP computation skipped: {exc}")

        if LABEL_ENCODER_PATH.exists():
            mlflow.log_artifact(LABEL_ENCODER_PATH.as_posix(), artifact_path="preprocessing")

        # 7. Log Model
        # Log xgboost explicitly or via scikit-learn
        LOCAL_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        model.save_model(LOCAL_MODEL_PATH.as_posix())
        # Use save_model + log_artifacts to stay compatible with older MLflow servers.
        with tempfile.TemporaryDirectory(prefix="mlflow-model-") as tmp_dir:
            local_model_dir = Path(tmp_dir) / "model"
            mlflow.xgboost.save_model(xgb_model=model, path=local_model_dir.as_posix())
            mlflow.log_artifacts(local_model_dir.as_posix(), artifact_path="model")

        registered_model_name = "slice-type-6g"
        if registered_model_name:
            active_run = mlflow.active_run()
            if active_run is not None:
                model_uri = f"runs:/{active_run.info.run_id}/model"
                try:
                    mlflow.register_model(model_uri, registered_model_name)
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] Model registration skipped for {registered_model_name}: {exc}")
            else:
                print("[WARN] No active MLflow run; skipping model registration.")
        finalize_model_lifecycle(
            model_name="slice_type_6g",
            model_family="xgboost_classifier",
            artifact_format="xgboost_ubj",
            metrics=metrics,
            local_artifact_path=LOCAL_MODEL_PATH,
            task_type="multiclass_classification",
            experiment_name=MLFLOW_EXPERIMENT_NAME,
            registered_model_name=registered_model_name,
            preprocessor_path=LABEL_ENCODER_PATH,
            input_schema={
                "features": [str(name) for name in feature_names],
                "shape": [None, int(X_test.shape[1])],
                "dtype": "float32",
            },
            model=model,
            export_kind="xgboost",
            export_basename="slice_type_6g",
            example_input=X_test[:1],
        )
        print("Logged model to MLflow (slice-type-6g).")

    print("-" * 50)
    print("Training Pipeline Complete.")
    print("-" * 50)


if __name__ == "__main__":
    main()
