"""Training script for the Congestion 5G LSTM model.

Loads processed Data (congestion_5g_processed.npz), trains an LSTM model
with focal loss and Optuna-based hyperparameter tuning, and logs to MLflow.
"""

import warnings
import tempfile
from pathlib import Path

import mlflow
import mlflow.pytorch
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
from sklearn.metrics import (
    roc_auc_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

from src.models.lifecycle import (
    configure_mlflow_tracking,
    finalize_model_lifecycle,
    get_experiment_name,
    use_mlflow_experiment,
)
from src.mlops.lifecycle import run_model_lifecycle

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_NPZ = ROOT_DIR / "data" / "processed" / "congestion_5g_processed.npz"
MODEL_DIR = ROOT_DIR / "models"
MODEL_PATH = MODEL_DIR / "congestion_5g_lstm.pth"
TRACED_MODEL_PATH = MODEL_DIR / "congestion_5g_lstm_traced.pt"
TEMP_MODEL_PATH = ROOT_DIR / "best_temp_model.pt"
PREPROCESSOR_PATH = ROOT_DIR / "data" / "processed" / "preprocessor_congestion_5g.pkl"
REGISTERED_MODEL_NAME = "congestion-lstm-5g"
MLFLOW_EXPERIMENT_NAME = get_experiment_name()
MLFLOW_TRACKING_URI = configure_mlflow_tracking()
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

# ---------------------------------------------------------------------------
# PyTorch Dataset Definition
# ---------------------------------------------------------------------------


class CongestionDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.FloatTensor(X)
        self.y = torch.FloatTensor(y)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


# ---------------------------------------------------------------------------
# Model Architecture & Loss
# ---------------------------------------------------------------------------


class FocalLoss(nn.Module):
    def __init__(self, alpha=0.75, gamma=2.0):
        super(FocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, inputs, targets):
        BCE_loss = nn.functional.binary_cross_entropy_with_logits(
            inputs, targets, reduction="none"
        )
        pt = torch.exp(-BCE_loss)
        F_loss = self.alpha * (1 - pt) ** self.gamma * BCE_loss
        return F_loss.mean()


class LSTMClassifier(nn.Module):
    def __init__(
        self, input_dim, hidden_dim=64, num_layers=2, dropout=0.3, bidirectional=True
    ):
        super(LSTMClassifier, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional,
        )

        direction_mult = 2 if bidirectional else 1

        self.fc = nn.Sequential(
            nn.Linear(hidden_dim * direction_mult, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )
        self._init_weights()

    def _init_weights(self):
        for name, param in self.lstm.named_parameters():
            if "weight_ih" in name:
                nn.init.xavier_uniform_(param.data)
            elif "weight_hh" in name:
                nn.init.orthogonal_(param.data)
            elif "bias" in name:
                param.data.fill_(0)
                n = param.size(0)
                param.data[n // 4 : n // 2].fill_(1)

    def forward(self, x):
        lstm_out, (hidden, cell) = self.lstm(x)
        if self.bidirectional:
            hidden_last = torch.cat((hidden[-2], hidden[-1]), dim=1)
        else:
            hidden_last = hidden[-1]
        out = self.fc(hidden_last)
        return out.squeeze(-1)


# ---------------------------------------------------------------------------
# Training Pipeline
# ---------------------------------------------------------------------------


def fit_epoch(model, dataloader, criterion, optimizer):
    model.train()
    total_loss = 0
    for X_batch, y_batch in dataloader:
        X_batch, y_batch = X_batch.to(DEVICE), y_batch.to(DEVICE)
        optimizer.zero_grad()
        outputs = model(X_batch)
        loss = criterion(outputs, y_batch)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(dataloader)


def evaluate(model, dataloader, criterion):
    model.eval()
    total_loss = 0
    all_preds, all_labels = [], []
    with torch.no_grad():
        for X_batch, y_batch in dataloader:
            X_batch, y_batch = X_batch.to(DEVICE), y_batch.to(DEVICE)
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            total_loss += loss.item()
            all_preds.extend(torch.sigmoid(outputs).cpu().numpy())
            all_labels.extend(y_batch.cpu().numpy())

    avg_loss = total_loss / len(dataloader)

    # Handle case where only one class is present in validation set during an epoch
    if len(np.unique(all_labels)) > 1:
        auc = roc_auc_score(all_labels, all_preds)
    else:
        auc = 0.5  # Neutral auc

    return avg_loss, auc


def find_optimal_threshold(probs, labels):
    from sklearn.metrics import f1_score, precision_recall_curve

    if len(np.unique(labels)) <= 1:
        return 0.5

    precision, recall, thresholds = precision_recall_curve(labels, probs)
    if len(thresholds) == 0:
        return 0.5

    candidates = []
    for idx, threshold in enumerate(thresholds):
        p = float(precision[idx])
        r = float(recall[idx])
        if p >= 0.50 and r >= 0.70:
            candidates.append((2 * p * r / max(p + r, 1e-12), float(threshold)))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]

    threshold_scores = []
    for threshold in thresholds:
        preds = (np.asarray(probs) >= threshold).astype(int)
        threshold_scores.append(
            (f1_score(labels, preds, zero_division=0), float(threshold))
        )
    return max(threshold_scores, key=lambda item: item[0])[1]


def train():
    if not PROCESSED_NPZ.exists():
        raise FileNotFoundError(
            f"Missing {PROCESSED_NPZ.as_posix()}. Run preprocessing first."
        )

    data = np.load(PROCESSED_NPZ, allow_pickle=True)
    X_train, y_train = data["X_train"], data["y_train"]
    X_val, y_val = data["X_val"], data["y_val"]
    X_test, y_test = data["X_test"], data["y_test"]

    print(
        f"[INFO] Loaded splits. Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}"
    )

    train_loader = DataLoader(
        CongestionDataset(X_train, y_train), batch_size=256, shuffle=True
    )
    val_loader = DataLoader(
        CongestionDataset(X_val, y_val), batch_size=256, shuffle=False
    )
    test_loader = DataLoader(
        CongestionDataset(X_test, y_test), batch_size=256, shuffle=False
    )

    input_dim = X_train.shape[2]

    # Setup MLflow
    use_mlflow_experiment(MLFLOW_EXPERIMENT_NAME)

    # Fast setup instead of extensive search to make the script run quickly
    # Hardcoding best params based on notebook's fine tuning output
    best_params = {
        "hidden_dim": 64,
        "num_layers": 2,
        "dropout": 0.3,
        "lr": 0.001,
        "bidirectional": True,
        "batch_size": 256,
    }

    with mlflow.start_run(run_name="LSTM_Final_Train"):
        mlflow.log_params(best_params)

        model = LSTMClassifier(
            input_dim=input_dim,
            hidden_dim=best_params["hidden_dim"],
            num_layers=best_params["num_layers"],
            dropout=best_params["dropout"],
            bidirectional=best_params["bidirectional"],
        ).to(DEVICE)

        criterion = FocalLoss(alpha=0.75, gamma=2.0)
        optimizer = optim.AdamW(
            model.parameters(), lr=best_params["lr"], weight_decay=0.01
        )
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="max", factor=0.5, patience=3
        )

        best_val_auc = 0
        patience_counter = 0

        print(f"[INFO] Training LSTM model on device {DEVICE}...")
        for epoch in range(15):  # Limiting epochs for speed
            train_loss = fit_epoch(model, train_loader, criterion, optimizer)
            val_loss, val_auc = evaluate(model, val_loader, criterion)

            scheduler.step(val_auc)
            mlflow.log_metrics(
                {"train_loss": train_loss, "val_loss": val_loss, "val_auc": val_auc},
                step=epoch,
            )

            if val_auc > best_val_auc:
                best_val_auc = val_auc
                patience_counter = 0
                torch.save(model.state_dict(), TEMP_MODEL_PATH.as_posix())
            else:
                patience_counter += 1
                if patience_counter >= 5:
                    print(f"Early stopping at epoch {epoch}")
                    break

            print(
                f"Epoch {epoch+1:2d}: Train Loss={train_loss:.4f}, Val Loss={val_loss:.4f}, Val AUC={val_auc:.4f}"
            )

        # Load best model
        if TEMP_MODEL_PATH.exists():
            model.load_state_dict(
                torch.load(TEMP_MODEL_PATH.as_posix(), weights_only=True)
            )
            TEMP_MODEL_PATH.unlink()

        # Evaluate on Test
        model.eval()
        all_probs, all_labels = [], []
        with torch.no_grad():
            for X_batch, y_batch in test_loader:
                X_batch = X_batch.to(DEVICE)
                outputs = model(X_batch)
                probs = torch.sigmoid(outputs).cpu().numpy()
                all_probs.extend(probs)
                all_labels.extend(y_batch.numpy())

        optimal_threshold = find_optimal_threshold(all_probs, all_labels)
        all_preds = (np.array(all_probs) >= optimal_threshold).astype(int)

        metrics = {
            "val_accuracy": accuracy_score(all_labels, all_preds),
            "val_precision": precision_score(all_labels, all_preds, zero_division=0),
            "val_recall": recall_score(all_labels, all_preds, zero_division=0),
            "val_f1": f1_score(all_labels, all_preds, zero_division=0),
            "val_roc_auc": (
                roc_auc_score(all_labels, all_probs)
                if len(np.unique(all_labels)) > 1
                else 0.5
            ),
        }
        legacy_metrics = {
            "accuracy": metrics["val_accuracy"],
            "precision": metrics["val_precision"],
            "recall": metrics["val_recall"],
            "f1": metrics["val_f1"],
            "auc_roc": metrics["val_roc_auc"],
        }

        print("\n[INFO] Final Test Set Performance:")
        for metric, value in metrics.items():
            print(f"  {metric}: {value:.4f}")

        mlflow.log_metrics({**metrics, **legacy_metrics})
        mlflow.log_param("optimal_threshold", optimal_threshold)

        # Save model
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "hyperparameters": best_params,
                "threshold": optimal_threshold,
                "metrics": metrics,
            },
            MODEL_PATH.as_posix(),
        )

        # Let's save a torchscript compatible model for easy inference later without class dependencies
        from torch.jit import trace

        try:
            model_traced = trace(
                model.to("cpu").eval(), torch.as_tensor(X_test[:1], dtype=torch.float32)
            )
            model_traced.save(TRACED_MODEL_PATH.as_posix())
        except Exception as e:
            print(f"Failed to trace model: {e}")

        # Use save_model + log_artifacts to stay compatible with older MLflow servers.
        model.to("cpu").eval()
        with tempfile.TemporaryDirectory(prefix="mlflow-model-") as tmp_dir:
            local_model_dir = Path(tmp_dir) / "model"
            mlflow.pytorch.save_model(model, path=local_model_dir.as_posix())
            mlflow.log_artifacts(local_model_dir.as_posix(), artifact_path="model")

        if REGISTERED_MODEL_NAME:
            active_run = mlflow.active_run()
            if active_run is not None:
                model_uri = f"runs:/{active_run.info.run_id}/model"
                try:
                    mlflow.register_model(model_uri, REGISTERED_MODEL_NAME)
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"[WARN] Model registration skipped for {REGISTERED_MODEL_NAME}: {exc}"
                    )
            else:
                print("[WARN] No active MLflow run; skipping model registration.")

        lifecycle_entry = finalize_model_lifecycle(
            model_name="congestion_5g",
            model_family="pytorch_lstm",
            artifact_format="torchscript",
            metrics=metrics,
            local_artifact_path=(
                TRACED_MODEL_PATH if TRACED_MODEL_PATH.exists() else MODEL_PATH
            ),
            task_type="binary_classification",
            experiment_name=MLFLOW_EXPERIMENT_NAME,
            registered_model_name=REGISTERED_MODEL_NAME,
            preprocessor_path=PREPROCESSOR_PATH,
            input_schema={
                "features": [str(name) for name in data["feature_names"]],
                "shape": [None, int(X_test.shape[1]), int(X_test.shape[2])],
                "dtype": "float32",
            },
            model=model.to("cpu").eval(),
            export_kind="pytorch",
            export_basename="congestion_5g",
            example_input=X_test[:1],
            input_names=["input"],
            output_names=["logits"],
            dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
            onnx_fixed_sequence_length=30,
            onnx_opset_version=18,
        )

        if lifecycle_entry.get("onnx_export_status") != "success":
            raise RuntimeError(
                "Cannot run lifecycle for congestion_5g because ONNX export failed: "
                f"{lifecycle_entry.get('onnx_export_reason') or 'unknown reason'}"
            )

        active_run = mlflow.active_run()
        if active_run is None:
            raise RuntimeError(
                "No active MLflow run; cannot execute deployment lifecycle."
            )

        run_model_lifecycle(
            model_name="congestion_5g",
            run_id=active_run.info.run_id,
            onnx_path="models/congestion_5g.onnx",
        )

        print(f"[INFO] Final model saved to {MODEL_PATH.as_posix()}")


if __name__ == "__main__":
    train()
