"""LightGBM multiclass model for Slice-Type prediction on the 5G dataset.

MLflow experiment : neuroslice-aiops
Registry name    : slice-type-lgbm-5g
Target classes   : loaded dynamically from the LabelEncoder (dataset uses integer types 1/2/3)
Primary metrics  : val_accuracy, val_f1 (weighted)
Quality gate     : val_accuracy >= 0.80
"""

import argparse
import tempfile
import warnings
from pathlib import Path

import joblib
import lightgbm as lgb
import matplotlib.pyplot as plt
import mlflow
import mlflow.lightgbm
import numpy as np
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from src.models.lifecycle import configure_mlflow_tracking, finalize_model_lifecycle, get_experiment_name, use_mlflow_experiment

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EXPERIMENT_NAME = get_experiment_name()
ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_NPZ = ROOT_DIR / "data" / "processed" / "slice_type_5g_processed.npz"
LABEL_ENCODER_PATH = ROOT_DIR / "data" / "processed" / "label_encoder_slice_type_5g.pkl"
LOCAL_MODEL_PATH = ROOT_DIR / "models" / "slice_type_5g_model.pkl"
REGISTERED_MODEL_NAME = "slice-type-lgbm-5g"
MLFLOW_TRACKING_URI = configure_mlflow_tracking()

# Class names are loaded dynamically from the label encoder at runtime
# (dataset uses integer labels 1/2/3, not string slice names)

# Default hyperparameters (notebook sweet-spot: n_estimators=20)
DEFAULT_N_ESTIMATORS = 20
DEFAULT_LEARNING_RATE = 0.05
DEFAULT_MAX_DEPTH = 3
DEFAULT_COLSAMPLE_BYTREE = 0.33
DEFAULT_REG_LAMBDA = 15.0
RANDOM_STATE = 12

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------
def evaluate_model(model, X_test, y_test, class_names):
    """Evaluate the model and return a metrics dict plus predictions."""
    y_pred = model.predict(X_test)
    y_pred_prob = model.predict_proba(X_test)  # shape (n_samples, n_classes)

    metrics = {
        "val_accuracy": float(accuracy_score(y_test, y_pred)),
        "val_precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
        "val_recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
        "val_f1": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
    }
    # Per-class F1 keyed by original label value (e.g. "1", "2", "3")
    per_class_f1 = f1_score(y_test, y_pred, average=None, zero_division=0)
    for cls_idx, cls_name in enumerate(class_names):
        metrics[f"val_f1_class_{cls_name}"] = float(per_class_f1[cls_idx])

    return metrics, y_pred, y_pred_prob


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------
def train(
    n_estimators: int = DEFAULT_N_ESTIMATORS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    max_depth: int = DEFAULT_MAX_DEPTH,
    colsample_bytree: float = DEFAULT_COLSAMPLE_BYTREE,
    reg_lambda: float = DEFAULT_REG_LAMBDA,
) -> None:
    """Train the LightGBM slice-type classifier and log everything to MLflow."""

    # -------------------------------------------------------------------
    # 1. Load processed data
    # -------------------------------------------------------------------
    if not PROCESSED_NPZ.exists():
        raise FileNotFoundError(
            f"Processed data not found at '{PROCESSED_NPZ.as_posix()}'. "
            "Run 'python src/data/preprocess_slice_type_5g.py' first."
        )

    data = np.load(PROCESSED_NPZ, allow_pickle=True)
    X_train = data["X_train"]
    y_train = data["y_train"]
    X_test = data["X_test"]
    y_test = data["y_test"]
    feature_names = list(data["feature_names"])

    # Load label encoder to decode predictions back to original labels
    if not LABEL_ENCODER_PATH.exists():
        raise FileNotFoundError(
            f"Label encoder not found at '{LABEL_ENCODER_PATH.as_posix()}'. "
            "Run 'python src/data/preprocess_slice_type_5g.py' first."
        )
    label_encoder = joblib.load(LABEL_ENCODER_PATH)
    # Use string representation of original labels for plot tick labels
    class_names = [str(c) for c in label_encoder.classes_]
    num_classes = len(class_names)

    print(f"[INFO] Loaded data — Train: {X_train.shape}, Test: {X_test.shape}")
    print(f"[INFO] Features : {feature_names}")
    print(f"[INFO] Classes  : {class_names}")

    # -------------------------------------------------------------------
    # 2. Build model
    # -------------------------------------------------------------------
    model = lgb.LGBMClassifier(
        objective="multiclass",
        num_class=num_classes,
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        colsample_bytree=colsample_bytree,
        reg_lambda=reg_lambda,
        random_state=RANDOM_STATE,
        verbose=-1,
        n_jobs=-1,
    )

    # -------------------------------------------------------------------
    # 3. MLflow run
    # -------------------------------------------------------------------
    use_mlflow_experiment(EXPERIMENT_NAME)
    with mlflow.start_run():
        # Log hyperparameters
        mlflow.log_params(
            {
                "n_estimators": n_estimators,
                "learning_rate": learning_rate,
                "max_depth": max_depth,
                "colsample_bytree": colsample_bytree,
                "reg_lambda": reg_lambda,
                "random_state": RANDOM_STATE,
                "num_classes": num_classes,
                "features": str(feature_names),
            }
        )

        # ---------------------------------------------------------------
        # 4. Train
        # ---------------------------------------------------------------
        print("[INFO] Training LightGBM multiclass classifier...")
        model.fit(X_train, y_train)

        # ---------------------------------------------------------------
        # 5. Evaluate
        # ---------------------------------------------------------------
        metrics, y_pred, y_pred_prob = evaluate_model(model, X_test, y_test, class_names)
        mlflow.log_metrics(metrics)

        print(f"\n{'=' * 55}")
        print("  Slice-Type-5G — LightGBM Results")
        print(f"{'=' * 55}")
        for k, v in metrics.items():
            print(f"  {k:<28} : {v:.4f}")

        report = classification_report(y_test, y_pred, target_names=class_names, zero_division=0)
        print(f"\n{report}")

        # ---------------------------------------------------------------
        # 6. Log figures
        # ---------------------------------------------------------------
        # Confusion matrix
        fig_cm, ax_cm = plt.subplots(figsize=(7, 6))
        cm = confusion_matrix(y_test, y_pred)
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=class_names,
            yticklabels=class_names,
            ax=ax_cm,
        )
        ax_cm.set_xlabel("Predicted Slice Type")
        ax_cm.set_ylabel("Actual Slice Type")
        ax_cm.set_title("Confusion Matrix — Slice-Type LightGBM")
        fig_cm.tight_layout()
        mlflow.log_figure(fig_cm, "confusion_matrix.png")
        plt.close(fig_cm)

        # Feature importance
        fig_imp, ax_imp = plt.subplots(figsize=(8, 5))
        importances = model.feature_importances_
        sorted_idx = np.argsort(importances)
        ax_imp.barh(
            [feature_names[i] for i in sorted_idx],
            importances[sorted_idx],
            color="#5c85d6",
        )
        ax_imp.set_xlabel("Importance (split)")
        ax_imp.set_title("Feature Importance — Slice-Type LightGBM")
        fig_imp.tight_layout()
        mlflow.log_figure(fig_imp, "feature_importance.png")
        plt.close(fig_imp)

        # SHAP global importance (mean |SHAP|, averaged over classes)
        try:
            import shap

            explainer = shap.TreeExplainer(model)
            # Use a sample for speed (up to 500 rows)
            sample_size = min(500, X_test.shape[0])
            X_sample = X_test[:sample_size]
            shap_values = explainer.shap_values(X_sample)
            # shap_values shape: (n_samples, n_features, n_classes)
            shap_arr = np.array(shap_values)
            if shap_arr.ndim == 3:
                shap_abs_mean = np.mean(np.abs(shap_arr), axis=(0, 2))
            else:
                shap_abs_mean = np.mean(np.abs(shap_arr), axis=0)

            fig_shap, ax_shap = plt.subplots(figsize=(8, 5))
            ax_shap.barh(feature_names, shap_abs_mean, color="steelblue")
            ax_shap.set_xlabel("Mean |SHAP value|")
            ax_shap.set_title("SHAP Global Feature Importance — Slice-Type LightGBM")
            ax_shap.invert_yaxis()
            fig_shap.tight_layout()
            mlflow.log_figure(fig_shap, "shap_global_importance.png")
            plt.close(fig_shap)
            print("[INFO] SHAP global importance chart logged.")
        except Exception as shap_exc:  # noqa: BLE001
            print(f"[WARN] SHAP logging skipped: {shap_exc}")

        # ---------------------------------------------------------------
        # 7. Log label encoder as artifact
        # ---------------------------------------------------------------
        if LABEL_ENCODER_PATH.exists():
            mlflow.log_artifact(LABEL_ENCODER_PATH.as_posix(), artifact_path="preprocessing")

        # ---------------------------------------------------------------
        # 8. Register model
        # ---------------------------------------------------------------
        LOCAL_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, LOCAL_MODEL_PATH)
        # Use save_model + log_artifacts to stay compatible with older MLflow servers.
        with tempfile.TemporaryDirectory(prefix="mlflow-model-") as tmp_dir:
            local_model_dir = Path(tmp_dir) / "model"
            mlflow.lightgbm.save_model(lgb_model=model, path=local_model_dir.as_posix())
            mlflow.log_artifacts(local_model_dir.as_posix(), artifact_path="model")

        if REGISTERED_MODEL_NAME:
            active_run = mlflow.active_run()
            if active_run is not None:
                model_uri = f"runs:/{active_run.info.run_id}/model"
                try:
                    mlflow.register_model(model_uri=model_uri, name=REGISTERED_MODEL_NAME)
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] Model registration skipped for {REGISTERED_MODEL_NAME}: {exc}")
            else:
                print("[WARN] No active MLflow run; skipping model registration.")

        finalize_model_lifecycle(
            model_name="slice_type_5g",
            model_family="lightgbm_classifier",
            artifact_format="lightgbm_joblib",
            metrics=metrics,
            local_artifact_path=LOCAL_MODEL_PATH,
            task_type="multiclass_classification",
            experiment_name=EXPERIMENT_NAME,
            preprocessor_path=LABEL_ENCODER_PATH,
            input_schema={
                "features": [str(name) for name in feature_names],
                "classes": [str(name) for name in class_names],
                "shape": [None, int(X_test.shape[1])],
                "dtype": "float32",
            },
            model=model,
            export_kind="lightgbm",
            export_basename="slice_type_5g",
            example_input=X_test[:1],
        )

        print(
            f"\n[DONE] Model registered as '{REGISTERED_MODEL_NAME}'. "
            f"val_accuracy={metrics['val_accuracy']:.4f} | val_f1={metrics['val_f1']:.4f}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Train Slice-Type-5G LightGBM classifier")
    parser.add_argument("--n_estimators", type=int, default=DEFAULT_N_ESTIMATORS)
    parser.add_argument("--learning_rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--max_depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--colsample_bytree", type=float, default=DEFAULT_COLSAMPLE_BYTREE)
    parser.add_argument("--reg_lambda", type=float, default=DEFAULT_REG_LAMBDA)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        max_depth=args.max_depth,
        colsample_bytree=args.colsample_bytree,
        reg_lambda=args.reg_lambda,
    )
