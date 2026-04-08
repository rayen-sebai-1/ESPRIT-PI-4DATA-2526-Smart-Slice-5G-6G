from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

ANOMALY_FEATURES = [
    "latency_gap_ns",
    "jitter_gap_ns",
    "packet_loss_gap",
    "data_rate_gap_gbps",
    "latency_ratio",
    "jitter_ratio",
    "packet_loss_ratio",
    "data_rate_ratio",
    "violation_count",
    "weighted_violation_score",
    "severity_score",
    "required_mobility_flag",
    "required_connectivity_flag",
    "slice_handover_flag",
    "slice_mismatch",
]

DEFAULT_DATASET_CANDIDATES = [
    Path("data/raw/network_slicing_dataset_v3.csv"),
    Path(r"C:\Users\DELL\Downloads\PI Data-20260406T215523Z-3-001\PI Data\dataset 5G et 6G\network_slicing_dataset - v3.csv"),
]


def resolve_dataset_path(cli_path: str | None) -> Path:
    candidates: list[Path] = []
    if cli_path:
        candidates.append(Path(cli_path))

    env_path = os.getenv("ANOMALY_DATASET_PATH")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(DEFAULT_DATASET_CANDIDATES)
    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = "\n".join(f"- {candidate}" for candidate in candidates)
    raise FileNotFoundError(f"Aucun dataset anomalies trouvé. Chemins vérifiés :\n{searched}")


def parse_yes_no(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().map({"yes": 1, "no": 0}).fillna(0).astype(int)


def compute_expected_slice_map(frame: pd.DataFrame) -> dict[str, str]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for use_case, slice_type in zip(frame["Use Case Type"], frame["Slice Type"]):
        grouped[str(use_case)][str(slice_type)] += 1
    return {use_case: counter.most_common(1)[0][0] for use_case, counter in grouped.items()}


def engineer_features(frame: pd.DataFrame, expected_slice_map: dict[str, str]) -> pd.DataFrame:
    dataset = frame.copy()

    numeric_columns = [
        "Packet Loss Budget",
        "Latency Budget (ns)",
        "Jitter Budget (ns)",
        "Data Rate Budget (Gbps)",
        "Slice Available Transfer Rate (Gbps)",
        "Slice Latency (ns)",
        "Slice Packet Loss",
        "Slice Jitter (ns)",
    ]
    for column in numeric_columns:
        dataset[column] = (
            dataset[column]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )

    dataset["required_mobility_flag"] = parse_yes_no(dataset["Required Mobility"])
    dataset["required_connectivity_flag"] = parse_yes_no(dataset["Required Connectivity"])
    dataset["slice_handover_flag"] = parse_yes_no(dataset["Slice Handover"])
    dataset["expected_slice_type"] = dataset["Use Case Type"].map(expected_slice_map)
    dataset["slice_mismatch"] = (dataset["Slice Type"] != dataset["expected_slice_type"]).astype(int)

    dataset["latency_gap_ns"] = (dataset["Slice Latency (ns)"] - dataset["Latency Budget (ns)"]).clip(lower=0)
    dataset["jitter_gap_ns"] = (dataset["Slice Jitter (ns)"] - dataset["Jitter Budget (ns)"]).clip(lower=0)
    dataset["packet_loss_gap"] = (dataset["Slice Packet Loss"] - dataset["Packet Loss Budget"]).clip(lower=0)
    dataset["data_rate_gap_gbps"] = (
        dataset["Data Rate Budget (Gbps)"] - dataset["Slice Available Transfer Rate (Gbps)"]
    ).clip(lower=0)

    dataset["latency_ratio"] = dataset["Slice Latency (ns)"] / dataset["Latency Budget (ns)"].clip(lower=1.0)
    dataset["jitter_ratio"] = dataset["Slice Jitter (ns)"] / dataset["Jitter Budget (ns)"].clip(lower=1.0)
    dataset["packet_loss_ratio"] = dataset["Slice Packet Loss"] / dataset["Packet Loss Budget"].clip(lower=1e-6)
    dataset["data_rate_ratio"] = dataset["Data Rate Budget (Gbps)"] / dataset["Slice Available Transfer Rate (Gbps)"].clip(lower=1.0)

    dataset["violation_count"] = (
        (dataset["latency_gap_ns"] > 0).astype(int)
        + (dataset["jitter_gap_ns"] > 0).astype(int)
        + (dataset["packet_loss_gap"] > 0).astype(int)
        + (dataset["data_rate_gap_gbps"] > 0).astype(int)
        + dataset["slice_mismatch"]
    )
    dataset["weighted_violation_score"] = (
        (dataset["latency_ratio"] * 0.28)
        + (dataset["jitter_ratio"] * 0.17)
        + (dataset["packet_loss_ratio"] * 0.22)
        + (dataset["data_rate_ratio"] * 0.18)
        + (dataset["required_mobility_flag"] * 0.05)
        + (dataset["required_connectivity_flag"] * 0.05)
        + (dataset["slice_handover_flag"] * 0.05)
        + (dataset["slice_mismatch"] * 0.25)
    )
    dataset["severity_score"] = (
        (dataset["weighted_violation_score"] / 4.0).clip(lower=0.0, upper=1.0) * 0.7
        + (dataset["violation_count"] / 5.0).clip(lower=0.0, upper=1.0) * 0.3
    ).clip(lower=0.0, upper=1.0)

    return dataset


def train_and_export(dataset_path: Path, output_dir: Path) -> None:
    frame = pd.read_csv(dataset_path, sep=";")
    expected_slice_map = compute_expected_slice_map(frame)
    engineered = engineer_features(frame, expected_slice_map)

    model = IsolationForest(
        n_estimators=250,
        contamination=0.08,
        random_state=42,
    )
    training_frame = engineered[ANOMALY_FEATURES].astype(float)
    model.fit(training_frame)

    decision_scores = model.decision_function(training_frame)
    anomaly_flags = model.predict(training_frame)
    anomaly_rate = float((anomaly_flags == -1).mean())

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model_anomaly_misrouting_isolation_forest.pkl"
    metadata_path = output_dir / "metadata_anomaly_misrouting.json"

    joblib.dump(model, model_path)

    metadata = {
        "model_name": "model_anomaly_misrouting_isolation_forest",
        "model_type": "IsolationForest",
        "source_notebook": "slice_misrouting_anomaly_pipeline.ipynb",
        "source_dataset": str(dataset_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "features": ANOMALY_FEATURES,
        "expected_slice_map": expected_slice_map,
        "decision_score_min": float(decision_scores.min()),
        "decision_score_max": float(decision_scores.max()),
        "estimated_anomaly_rate": round(anomaly_rate, 4),
        "rows_count": int(len(frame)),
        "notes": [
            "Operational anomaly adapter trained on engineered gap and mismatch features from the V3 dataset.",
            "The provider combines IsolationForest output with runtime severity and misrouting checks.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[anomaly-export] Artefacts générés avec succès.")
    print(f"[anomaly-export] Dataset source : {dataset_path}")
    print(f"[anomaly-export] Taux d'anomalie estimé : {anomaly_rate:.4f}")
    print(f"[anomaly-export] Modèle : {model_path}")
    print(f"[anomaly-export] Metadata : {metadata_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporte les artefacts anomalies/misrouting du MVP NeuroSlice Tunisia.")
    parser.add_argument("--dataset", help="Chemin vers le dataset V3 anomalies.", default=None)
    parser.add_argument("--output-dir", default="data/models/anomaly", help="Dossier de sortie des artefacts.")
    args = parser.parse_args()

    dataset_path = resolve_dataset_path(args.dataset)
    train_and_export(dataset_path=dataset_path, output_dir=Path(args.output_dir))


if __name__ == "__main__":
    main()
