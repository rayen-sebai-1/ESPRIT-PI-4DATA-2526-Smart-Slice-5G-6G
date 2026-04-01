"""LSTM-based congestion time-series forecasting model for the 6G dataset.

MLflow experiment : congestion-forecast-6g
Registry name    : congestion-lstm-6g
Primary metrics  : val_mae, val_rmse
Quality gate     : val_mae < 5.0
"""

import os
import warnings

import matplotlib.pyplot as plt
import mlflow
import mlflow.pytorch
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error
from torch.utils.data import DataLoader, Dataset

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EXPERIMENT_NAME = "congestion-forecast-6g"
DATA_PATH = "data/processed/6g_processed.csv"
REGISTERED_MODEL_NAME = "congestion-lstm-6g"

SEQ_LENGTH = 24
LSTM_UNITS = 128
EPOCHS = 50
LEARNING_RATE = 1e-3
BATCH_SIZE = 64
TRAIN_SPLIT = 0.8

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class CongestionDataset(Dataset):
    """Sliding-window dataset for the LSTM model."""

    def __init__(self, sequences: np.ndarray, targets: np.ndarray):
        self.sequences = torch.tensor(sequences, dtype=torch.float32)
        self.targets = torch.tensor(targets, dtype=torch.float32)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return self.sequences[idx], self.targets[idx]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
class CongestionLSTM(nn.Module):
    """Single-layer LSTM that predicts the next CPU-utilisation value."""

    def __init__(self, input_size: int = 2, hidden_size: int = LSTM_UNITS, num_layers: int = 1):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # x: (B, T, F)
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])  # (B, 1)


# ---------------------------------------------------------------------------
# Sequence builder
# ---------------------------------------------------------------------------
def build_sequences(df: pd.DataFrame, seq_length: int = SEQ_LENGTH):
    """Return (X, y) numpy arrays from the processed DataFrame."""
    values = df[["cpu_utilization", "bandwidth_mbps"]].values.astype(np.float32)
    targets = df["cpu_utilization"].values.astype(np.float32)

    X, y = [], []
    for i in range(len(values) - seq_length):
        X.append(values[i : i + seq_length])
        y.append(targets[i + seq_length])
    return np.array(X), np.array(y)


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------
def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def _evaluate(model: nn.Module, loader: DataLoader) -> tuple:
    model.eval()
    all_preds, all_targets = [], []
    with torch.no_grad():
        for X_batch, y_batch in loader:
            X_batch = X_batch.to(DEVICE)
            preds = model(X_batch).cpu().squeeze().numpy()
            all_preds.extend(preds.tolist())
            all_targets.extend(y_batch.numpy().tolist())

    y_true = np.array(all_targets)
    y_pred = np.array(all_preds)
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mape = _mape(y_true, y_pred)
    return mae, rmse, mape


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------
def train(
    seq_length: int = SEQ_LENGTH,
    lstm_units: int = LSTM_UNITS,
    epochs: int = EPOCHS,
    learning_rate: float = LEARNING_RATE,
) -> None:
    """Train the LSTM model and log everything to MLflow."""

    # -----------------------------------------------------------------------
    # 1. Load & split data
    # -----------------------------------------------------------------------
    df = pd.read_csv(DATA_PATH)
    print(f"[INFO] Loaded {len(df)} rows from '{DATA_PATH}'.")

    X, y = build_sequences(df, seq_length)
    split_idx = int(len(X) * TRAIN_SPLIT)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    print(f"[INFO] Train: {len(X_train)}, Val: {len(X_val)} sequences.")

    train_ds = CongestionDataset(X_train, y_train)
    val_ds = CongestionDataset(X_val, y_val)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    # -----------------------------------------------------------------------
    # 2. Build model
    # -----------------------------------------------------------------------
    model = CongestionLSTM(input_size=2, hidden_size=lstm_units).to(DEVICE)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    # -----------------------------------------------------------------------
    # 3. MLflow run
    # -----------------------------------------------------------------------
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run():
        # Log hyperparameters
        mlflow.log_params(
            {
                "seq_length": seq_length,
                "lstm_units": lstm_units,
                "epochs": epochs,
                "learning_rate": learning_rate,
            }
        )

        train_losses, val_maes = [], []

        # -------------------------------------------------------------------
        # 4. Training loop
        # -------------------------------------------------------------------
        for epoch in range(1, epochs + 1):
            model.train()
            epoch_loss = 0.0
            for X_batch, y_batch in train_loader:
                X_batch, y_batch = X_batch.to(DEVICE), y_batch.to(DEVICE)
                optimizer.zero_grad()
                preds = model(X_batch).squeeze()
                loss = criterion(preds, y_batch)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item() * len(X_batch)

            epoch_loss /= len(train_ds)
            val_mae, val_rmse, val_mape = _evaluate(model, val_loader)

            train_losses.append(epoch_loss)
            val_maes.append(val_mae)

            mlflow.log_metrics(
                {
                    "train_loss": epoch_loss,
                    "val_mae": val_mae,
                    "val_rmse": val_rmse,
                    "val_mape": val_mape,
                },
                step=epoch,
            )

            if epoch % 10 == 0 or epoch == 1:
                print(
                    f"[Epoch {epoch:3d}/{epochs}] "
                    f"loss={epoch_loss:.4f} | "
                    f"val_mae={val_mae:.4f} | "
                    f"val_rmse={val_rmse:.4f}"
                )

        # -------------------------------------------------------------------
        # 5. Save training curves as figures
        # -------------------------------------------------------------------
        fig_loss, ax_loss = plt.subplots()
        ax_loss.plot(range(1, epochs + 1), train_losses, label="Train Loss")
        ax_loss.set_xlabel("Epoch")
        ax_loss.set_ylabel("MSE Loss")
        ax_loss.set_title("Training Loss Curve")
        ax_loss.legend()
        mlflow.log_figure(fig_loss, "train_loss_curve.png")
        plt.close(fig_loss)

        fig_mae, ax_mae = plt.subplots()
        ax_mae.plot(range(1, epochs + 1), val_maes, label="Val MAE", color="orange")
        ax_mae.set_xlabel("Epoch")
        ax_mae.set_ylabel("MAE")
        ax_mae.set_title("Validation MAE Curve")
        ax_mae.legend()
        mlflow.log_figure(fig_mae, "val_mae_curve.png")
        plt.close(fig_mae)

        # -------------------------------------------------------------------
        # 6. Register model
        # -------------------------------------------------------------------
        mlflow.pytorch.log_model(
            model,
            artifact_path="model",
            registered_model_name=REGISTERED_MODEL_NAME,
        )

        final_mae, final_rmse, final_mape = _evaluate(model, val_loader)
        mlflow.log_metrics(
            {
                "final_val_mae": final_mae,
                "final_val_rmse": final_rmse,
                "final_val_mape": final_mape,
            }
        )

        print(
            f"\n[DONE] Final metrics – "
            f"val_mae={final_mae:.4f} | "
            f"val_rmse={final_rmse:.4f} | "
            f"val_mape={final_mape:.4f}"
        )


if __name__ == "__main__":
    train()
