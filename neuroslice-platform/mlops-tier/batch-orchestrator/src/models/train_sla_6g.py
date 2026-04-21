"""XGBoost-based SLA adherence model for the 6G dataset.

MLflow experiment : sla-adherence-6g
Registry name    : sla-xgboost-6g
Primary metrics  : val_roc_auc, val_f1, val_accuracy
Quality gate     : val_roc_auc >= 0.75

Features (14 total):
  Temporal QoS (9): lag-1, rolling-mean (w=5), rolling-std for
      Slice Latency (ns), Slice Packet Loss, Slice Jitter (ns)
  Context (5): Slice Type Encoded, Mobility Encoded, Connectivity Encoded,
               Handover Encoded, Slice Available Transfer Rate (Gbps)
"""

import argparse
import os
import warnings

import matplotlib.pyplot as plt
import mlflow
import mlflow.xgboost
import numpy as np

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EXPERIMENT_NAME = "sla-adherence-6g"
PROCESSED_NPZ = "data/processed/sla_6g_processed.npz"
SCALER_PATH = "data/processed/scaler_sla_6g.pkl"
REGISTERED_MODEL_NAME = "sla-xgboost-6g"
MLFLOW_TRACKING_URI = "sqlite:///mlflow.db"

DEFAULT_N_ESTIMATORS = 300
DEFAULT_MAX_DEPTH = 6
DEFAULT_LEARNING_RATE = 0.05
DEFAULT_SUBSAMPLE = 0.8
DEFAULT_COLSAMPLE_BYTREE = 0.8

RANDOM_STATE = 42
QUALITY_GATE_ROC_AUC = 0.75

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------
def evaluate_model(model, X_test, y_test):
    """Evaluate the model and return a metrics dict, predictions, and probabilities."""
    y_pred = model.predict(X_test)
    y_pred_prob = model.predict_proba(X_test)[:, 1]

    metrics = {
        "val_accuracy": float(accuracy_score(y_test, y_pred)),
        "val_precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "val_recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "val_f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "val_roc_auc": float(roc_auc_score(y_test, y_pred_prob)),
    }
    return metrics, y_pred, y_pred_prob


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------
def train(
    n_estimators: int = DEFAULT_N_ESTIMATORS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    max_depth: int = DEFAULT_MAX_DEPTH,
    subsample: float = DEFAULT_SUBSAMPLE,
    colsample_bytree: float = DEFAULT_COLSAMPLE_BYTREE,
) -> None:
    """Train the XGBoost SLA-6G model and log everything to MLflow."""

    # -------------------------------------------------------------------
    # 1. Load processed data
    # -------------------------------------------------------------------
    if not os.path.exists(PROCESSED_NPZ):
        raise FileNotFoundError(
            f"Processed data not found at '{PROCESSED_NPZ}'. "
            "Run 'python src/data/preprocess_sla_6g.py' first."
        )

    data = np.load(PROCESSED_NPZ, allow_pickle=True)
    X_train = data["X_train"]
    y_train = data["y_train"]
    X_test = data["X_test"]
    y_test = data["y_test"]
    feature_names = list(data["feature_names"])

    print(f"[INFO] Loaded data — Train: {X_train.shape}, Test: {X_test.shape}")
    print(f"[INFO] Features ({len(feature_names)}): {feature_names}")

    # Compute scale_pos_weight from class imbalance
    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())
    scale_pos_weight = n_neg / max(n_pos, 1)
    print(f"[INFO] scale_pos_weight: {scale_pos_weight:.4f}")

    # -------------------------------------------------------------------
    # 2. Build model
    # -------------------------------------------------------------------
    model = XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    # -------------------------------------------------------------------
    # 3. MLflow run
    # -------------------------------------------------------------------
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run():
        mlflow.log_params(
            {
                "n_estimators": n_estimators,
                "max_depth": max_depth,
                "learning_rate": learning_rate,
                "subsample": subsample,
                "colsample_bytree": colsample_bytree,
                "scale_pos_weight": round(scale_pos_weight, 4),
                "random_state": RANDOM_STATE,
                "features": str(feature_names),
                "n_features": len(feature_names),
            }
        )

        # ---------------------------------------------------------------
        # 4. Train
        # ---------------------------------------------------------------
        print("[INFO] Training XGBoost classifier (sla-xgboost-6g)...")
        model.fit(X_train, y_train)

        # ---------------------------------------------------------------
        # 5. Evaluate
        # ---------------------------------------------------------------
        metrics, y_pred, y_pred_prob = evaluate_model(model, X_test, y_test)
        mlflow.log_metrics(metrics)

        print(f"\n{'=' * 55}")
        print("  SLA Adherence — XGBoost 6G Results")
        print(f"{'=' * 55}")
        for k, v in metrics.items():
            print(f"  {k:<18} : {v:.4f}")

        target_names = ["SLA non respecté", "SLA respecté"]
        report = classification_report(y_test, y_pred, target_names=target_names)
        print(f"\n{report}")

        # ---------------------------------------------------------------
        # 6. Log figures
        # ---------------------------------------------------------------
        # Confusion matrix
        fig_cm, ax_cm = plt.subplots(figsize=(6, 5))
        cm = confusion_matrix(y_test, y_pred)
        im = ax_cm.imshow(cm, cmap="Blues")
        ax_cm.set_xticks([0, 1])
        ax_cm.set_yticks([0, 1])
        ax_cm.set_xticklabels(target_names, fontsize=9)
        ax_cm.set_yticklabels(target_names, fontsize=9)
        ax_cm.set_xlabel("Predicted")
        ax_cm.set_ylabel("Actual")
        ax_cm.set_title("Confusion Matrix — SLA XGBoost 6G")
        for i in range(2):
            for j in range(2):
                ax_cm.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=14)
        fig_cm.colorbar(im)
        fig_cm.tight_layout()
        mlflow.log_figure(fig_cm, "confusion_matrix.png")
        plt.close(fig_cm)

        # ROC curve
        fig_roc, ax_roc = plt.subplots(figsize=(6, 5))
        fpr, tpr, _ = roc_curve(y_test, y_pred_prob)
        ax_roc.plot(fpr, tpr, label=f"ROC AUC = {metrics['val_roc_auc']:.4f}")
        ax_roc.plot([0, 1], [0, 1], "--", color="gray")
        ax_roc.set_xlabel("False Positive Rate")
        ax_roc.set_ylabel("True Positive Rate")
        ax_roc.set_title("ROC Curve — SLA XGBoost 6G")
        ax_roc.legend()
        fig_roc.tight_layout()
        mlflow.log_figure(fig_roc, "roc_curve.png")
        plt.close(fig_roc)

        # Feature importance
        fig_imp, ax_imp = plt.subplots(figsize=(10, 6))
        importances = model.feature_importances_
        sorted_idx = np.argsort(importances)
        display_names = [feature_names[i] for i in sorted_idx]
        ax_imp.barh(display_names, importances[sorted_idx], color="#2ecc71")
        ax_imp.set_xlabel("Importance")
        ax_imp.set_title("Feature Importance — SLA XGBoost 6G")
        fig_imp.tight_layout()
        mlflow.log_figure(fig_imp, "feature_importance.png")
        plt.close(fig_imp)

        # ---------------------------------------------------------------
        # 7. SHAP explainability
        # ---------------------------------------------------------------
        try:
            import shap

            print("[INFO] Computing SHAP values...")
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_test)

            # Global SHAP bar chart (mean |SHAP|)
            fig_shap, ax_shap = plt.subplots(figsize=(10, 6))
            mean_shap = np.abs(shap_values).mean(axis=0)
            shap_sorted_idx = np.argsort(mean_shap)
            ax_shap.barh(
                [feature_names[i] for i in shap_sorted_idx],
                mean_shap[shap_sorted_idx],
                color="#3498db",
            )
            ax_shap.set_xlabel("Mean |SHAP value|")
            ax_shap.set_title("SHAP Global Feature Importance — SLA 6G")
            fig_shap.tight_layout()
            mlflow.log_figure(fig_shap, "shap_global_importance.png")
            plt.close(fig_shap)

            print(f"[INFO] SHAP computed for {len(X_test)} test samples.")
        except Exception as shap_exc:  # noqa: BLE001
            print(f"[WARN] SHAP computation skipped: {shap_exc}")

        # ---------------------------------------------------------------
        # 8. Log scaler as artifact
        # ---------------------------------------------------------------
        if os.path.exists(SCALER_PATH):
            mlflow.log_artifact(SCALER_PATH, artifact_path="preprocessing")

        # ---------------------------------------------------------------
        # 9. Register model
        # ---------------------------------------------------------------
        mlflow.xgboost.log_model(
            model,
            artifact_path="model",
            registered_model_name=REGISTERED_MODEL_NAME,
        )

        roc_auc = metrics["val_roc_auc"]
        gate_status = "PASS" if roc_auc >= QUALITY_GATE_ROC_AUC else "FAIL"
        print(
            f"\n[DONE] Model registered as '{REGISTERED_MODEL_NAME}'. "
            f"val_roc_auc={roc_auc:.4f} — Quality gate: {gate_status} (>= {QUALITY_GATE_ROC_AUC})"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Train SLA-6G adherence XGBoost model")
    parser.add_argument("--n_estimators", type=int, default=DEFAULT_N_ESTIMATORS)
    parser.add_argument("--learning_rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--max_depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--subsample", type=float, default=DEFAULT_SUBSAMPLE)
    parser.add_argument("--colsample_bytree", type=float, default=DEFAULT_COLSAMPLE_BYTREE)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        max_depth=args.max_depth,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
    )
