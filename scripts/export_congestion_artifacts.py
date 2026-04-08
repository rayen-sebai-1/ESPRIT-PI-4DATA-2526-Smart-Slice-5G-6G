from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

FEATURE_COLUMNS = [
    "cpu_util_pct",
    "mem_util_pct",
    "bw_util_pct",
    "active_users",
    "queue_len",
    "hour",
    "slice_type_encoded",
]

DEFAULT_DATASET_CANDIDATES = [
    Path("data/raw/network_slicing_dataset_enriched_timeseries.csv"),
    Path(
        r"C:\Users\DELL\Downloads\PI Data-20260406T215523Z-3-001\PI Data\dataset 5G et 6G\network_slicing_dataset_enriched_timeseries.csv"
    ),
]

SLICE_ALIASES = {
    "eMBB": "feMBB",
    "URLLC": "mURLLC",
    "mMTC": "umMTC",
}


def resolve_dataset_path(cli_path: str | None) -> Path:
    candidates: list[Path] = []
    if cli_path:
        candidates.append(Path(cli_path))

    env_path = os.getenv("CONGESTION_DATASET_PATH")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(DEFAULT_DATASET_CANDIDATES)
    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = "\n".join(f"- {candidate}" for candidate in candidates)
    raise FileNotFoundError(f"Aucun dataset de congestion trouvé. Chemins vérifiés :\n{searched}")


def train_and_export(dataset_path: Path, output_dir: Path) -> None:
    dataframe = pd.read_csv(dataset_path)
    dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"], errors="coerce")
    dataframe["hour"] = dataframe["timestamp"].dt.hour.fillna(0).astype(int)

    slice_types = sorted(dataframe["slice_type"].dropna().unique().tolist())
    slice_mapping = {slice_name: index for index, slice_name in enumerate(slice_types)}
    dataframe["slice_type_encoded"] = dataframe["slice_type"].map(slice_mapping).astype(int)
    dataframe["congestion_flag"] = dataframe["congestion_flag"].astype(int)

    features = dataframe[FEATURE_COLUMNS].astype(float)
    target = dataframe["congestion_flag"]

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.20,
        random_state=42,
        stratify=target,
    )

    class_counts = Counter(y_train.tolist())
    negative_count = max(class_counts.get(0, 1), 1)
    positive_count = max(class_counts.get(1, 1), 1)
    positive_weight = negative_count / positive_count
    sample_weights = np.where(y_train == 1, positive_weight, 1.0)

    model = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_depth=5,
        max_iter=240,
        min_samples_leaf=25,
        random_state=42,
    )
    model.fit(x_train, y_train, sample_weight=sample_weights)

    predicted_labels = model.predict(x_test)
    predicted_scores = model.predict_proba(x_test)[:, 1]

    accuracy = accuracy_score(y_test, predicted_labels)
    roc_auc = roc_auc_score(y_test, predicted_scores)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model_congestion_timeseries_boosting.pkl"
    metadata_path = output_dir / "metadata_congestion_timeseries.json"

    joblib.dump(model, model_path)

    metadata = {
        "model_name": "model_congestion_timeseries_boosting",
        "model_type": "HistGradientBoostingClassifier",
        "source_notebook": "network_slicing_congestion_LSTM.ipynb",
        "source_dataset": str(dataset_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "features": FEATURE_COLUMNS,
        "target": "congestion_flag",
        "slice_mapping": slice_mapping,
        "slice_aliases": SLICE_ALIASES,
        "class_distribution": dict(Counter(target.tolist())),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "metrics": {
            "accuracy": round(float(accuracy), 4),
            "roc_auc": round(float(roc_auc), 4),
        },
        "notes": [
            "Operational congestion adapter trained on the provided time-series telemetry dataset.",
            "This is dataset-aligned and docker-friendly; it is not a direct PyTorch LSTM export.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[congestion-export] Artefacts générés avec succès.")
    print(f"[congestion-export] Dataset source : {dataset_path}")
    print(f"[congestion-export] Accuracy test : {accuracy:.4f}")
    print(f"[congestion-export] ROC AUC test : {roc_auc:.4f}")
    print(f"[congestion-export] Modèle : {model_path}")
    print(f"[congestion-export] Metadata : {metadata_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporte les artefacts de congestion du MVP NeuroSlice Tunisia.")
    parser.add_argument("--dataset", help="Chemin vers le dataset temporel de congestion.", default=None)
    parser.add_argument("--output-dir", default="data/models/congestion", help="Dossier de sortie des artefacts.")
    args = parser.parse_args()

    dataset_path = resolve_dataset_path(args.dataset)
    train_and_export(dataset_path=dataset_path, output_dir=Path(args.output_dir))


if __name__ == "__main__":
    main()
