"""Training script for the Slice-Type 6G model.

Uses XGBoost to train a multiclass classifier for the 5 6G slice types.
Integrates with MLflow to track parameters, evaluation metrics, and SHAP summary plots.
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb
import mlflow
import shap

# Configuration
NPZ_PATH = os.path.join("data", "processed", "slice_type_6g_processed.npz")
MLFLOW_EXPERIMENT_NAME = "slice-type-6g"


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
    if not os.path.exists(NPZ_PATH):
        print(f"[ERROR] Processed data not found at '{NPZ_PATH}'. Please run preprocessing.")
        sys.exit(1)

    print(f"Loading data from {NPZ_PATH}...")
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
    experiment_id = get_or_create_experiment(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(experiment_id=experiment_id, run_name="xgboost_multi_classifier"):
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
        # XGBoost TreeExplainer handles XGBClassifier seamlessly
        explainer = shap.TreeExplainer(model)
        # Using a subset of training data for faster SHAP computation if necessary,
        # but 8000 samples should be fast for XGBoost.
        # To avoid massive dot generation, we sample down.
        sample_idx = np.random.choice(X_train.shape[0], min(X_train.shape[0], 2000), replace=False)
        X_train_sample = X_train[sample_idx]
        shap_values = explainer.shap_values(X_train_sample)

        plt.figure(figsize=(10, 8))
        shap.summary_plot(shap_values, X_train_sample, feature_names=feature_names, show=False)

        os.makedirs("artifacts", exist_ok=True)
        shap_plot_path = os.path.join("artifacts", "shap_summary_6g.png")
        plt.tight_layout()
        plt.savefig(shap_plot_path, bbox_inches='tight')
        plt.close()

        mlflow.log_artifact(shap_plot_path)
        print(f"Logged SHAP artifact: {shap_plot_path}")

        # 7. Log Model
        # Log xgboost explicitly or via scikit-learn
        mlflow.xgboost.log_model(
             xgb_model=model,
             artifact_path="model",
             registered_model_name="slice-type-6g"
        )
        print("Logged model to MLflow (slice-type-6g).")

    print("-" * 50)
    print("Training Pipeline Complete.")
    print("-" * 50)


if __name__ == "__main__":
    main()
