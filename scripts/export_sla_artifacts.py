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
from sklearn.preprocessing import StandardScaler

SLA_FEATURES = [
    "Packet Loss Rate",
    "Packet delay",
    "Smart City & Home",
    "IoT Devices",
    "Public Safety",
]

DEFAULT_DATASET_CANDIDATES = [
    Path("data/raw/train_dataset.csv"),
    Path(r"C:\Users\DELL\Downloads\PI Data-20260406T215523Z-3-001\PI Data\dataset 5G et 6G\train_dataset.csv"),
]


def resolve_dataset_path(cli_path: str | None) -> Path:
    candidates: list[Path] = []
    if cli_path:
        candidates.append(Path(cli_path))

    env_path = os.getenv("SLA_DATASET_PATH")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(DEFAULT_DATASET_CANDIDATES)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = "\n".join(f"- {candidate}" for candidate in candidates)
    raise FileNotFoundError(f"Aucun dataset SLA trouvé. Chemins vérifiés :\n{searched}")


def build_sla_labels(dataframe: pd.DataFrame) -> pd.Series:
    public_safety = dataframe["Public Safety"].astype(int)
    smart_city = dataframe["Smart City & Home"].astype(int)
    iot_devices = dataframe["IoT Devices"].astype(int)
    packet_delay = dataframe["Packet delay"].astype(float)
    packet_loss = dataframe["Packet Loss Rate"].astype(float)
    is_5g = dataframe.get("LTE/5G", pd.Series(np.zeros(len(dataframe)), index=dataframe.index)).astype(int)
    is_gbr = dataframe.get("GBR", pd.Series(np.zeros(len(dataframe)), index=dataframe.index)).astype(int)

    delay_limit = np.select(
        [public_safety == 1, smart_city == 1, iot_devices == 1],
        [60.0, 105.0, 170.0],
        default=130.0,
    )
    loss_limit = np.select(
        [public_safety == 1, smart_city == 1, iot_devices == 1],
        [0.0015, 0.0030, 0.0045],
        default=0.0035,
    )

    delay_limit = delay_limit + (is_5g * 10.0) + (is_gbr * 5.0)
    loss_limit = loss_limit + (is_5g * 0.0004) + (is_gbr * 0.0002)

    latency_margin = (delay_limit - packet_delay) / delay_limit
    loss_margin = (loss_limit - packet_loss) / loss_limit
    composite_margin = (0.58 * latency_margin) + (0.42 * loss_margin)

    return (composite_margin >= -0.08).astype(int)


def export_artifacts(dataset_path: Path, output_dir: Path, save_prepared_dataset: bool) -> None:
    dataframe = pd.read_csv(dataset_path)
    missing_columns = [column for column in SLA_FEATURES if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans le dataset SLA : {missing_columns}")

    dataframe["sla_met"] = build_sla_labels(dataframe)
    features_frame = dataframe[SLA_FEATURES].astype(float)
    target = dataframe["sla_met"].astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        features_frame,
        target,
        test_size=0.20,
        random_state=42,
        stratify=target,
    )

    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)
    x_test_scaled = scaler.transform(x_test)

    class_counts = Counter(y_train.tolist())
    negative_count = max(class_counts.get(0, 1), 1)
    positive_count = max(class_counts.get(1, 1), 1)
    scale_pos_weight = negative_count / positive_count

    model = HistGradientBoostingClassifier(
        learning_rate=0.06,
        max_depth=4,
        max_iter=220,
        min_samples_leaf=20,
        random_state=42,
    )
    sample_weights = np.where(y_train == 1, scale_pos_weight, 1.0)
    model.fit(x_train_scaled, y_train, sample_weight=sample_weights)

    predicted_labels = model.predict(x_test_scaled)
    predicted_scores = model.predict_proba(x_test_scaled)[:, 1]

    accuracy = accuracy_score(y_test, predicted_labels)
    roc_auc = roc_auc_score(y_test, predicted_scores)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model_b_sla_5g_boosting.pkl"
    scaler_path = output_dir / "scaler_sla_5g.pkl"
    metadata_path = output_dir / "metadata_model_b.json"

    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    metadata = {
        "model_name": "model_b_sla_5g_boosting",
        "model_type": "HistGradientBoostingClassifier",
        "source_notebook": "SLA_5G_Modeling.ipynb",
        "source_dataset": str(dataset_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "features": SLA_FEATURES,
        "target": "sla_met",
        "class_distribution": dict(Counter(target.tolist())),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "metrics": {
            "accuracy": round(float(accuracy), 4),
            "roc_auc": round(float(roc_auc), 4),
        },
        "notes": [
            "Target sla_met generated from deterministic telecom-oriented SLA rules.",
            "Provider expects packet loss as a rate. If the runtime session stores a percent-like value, it is normalized.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    if save_prepared_dataset:
        prepared_path = output_dir / "5G_prepared.csv"
        dataframe.to_csv(prepared_path, index=False)

    print("[sla-export] Artefacts générés avec succès.")
    print(f"[sla-export] Dataset source : {dataset_path}")
    print(f"[sla-export] Accuracy test : {accuracy:.4f}")
    print(f"[sla-export] ROC AUC test : {roc_auc:.4f}")
    print(f"[sla-export] Modèle : {model_path}")
    print(f"[sla-export] Scaler : {scaler_path}")
    print(f"[sla-export] Metadata : {metadata_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporte les artefacts SLA du MVP NeuroSlice Tunisia.")
    parser.add_argument("--dataset", help="Chemin vers le train_dataset.csv ou un dataset compatible.", default=None)
    parser.add_argument("--output-dir", default="data/models/sla", help="Dossier de sortie des artefacts.")
    parser.add_argument(
        "--save-prepared-dataset",
        action="store_true",
        help="Sauvegarde également un CSV préparé avec la colonne sla_met.",
    )
    args = parser.parse_args()

    dataset_path = resolve_dataset_path(args.dataset)
    export_artifacts(
        dataset_path=dataset_path,
        output_dir=Path(args.output_dir),
        save_prepared_dataset=args.save_prepared_dataset,
    )


if __name__ == "__main__":
    main()
