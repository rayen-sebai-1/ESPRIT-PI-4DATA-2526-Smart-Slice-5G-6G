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

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from packages.neuroslice_common.prediction_common import SLICE_FEATURES

RAW_SLICE_TARGET_MAP = {
    "1": "eMBB",
    "2": "mMTC",
    "3": "URLLC",
}

RUNTIME_FEATURE_MAPPING = {
    "LTE/5g Category": "sessions.lte_5g_category",
    "Packet Loss Rate": "normalize_packet_loss(sessions.packet_loss)",
    "Packet delay": "sessions.latency_ms",
    "Smartphone": "sessions.smartphone",
    "IoT Devices": "sessions.iot_devices",
    "GBR": "sessions.gbr",
}

DEFAULT_DATASET_CANDIDATES = [
    Path("data/raw/train_dataset.csv"),
    Path(r"C:\Users\DELL\Downloads\PI Data-20260406T215523Z-3-001\PI Data\dataset 5G et 6G\train_dataset.csv"),
]

PACKET_DELAY_DIVISOR = 5.0


def simplify_tree(node: dict) -> dict:
    if "leaf_value" in node:
        return {"leaf_value": float(node["leaf_value"])}

    return {
        "split_feature": int(node["split_feature"]),
        "threshold": float(node["threshold"]),
        "decision_type": str(node.get("decision_type", "<=")),
        "default_left": bool(node.get("default_left", True)),
        "missing_type": str(node.get("missing_type", "None")),
        "left_child": simplify_tree(node["left_child"]),
        "right_child": simplify_tree(node["right_child"]),
    }


def resolve_dataset_path(cli_path: str | None) -> Path:
    candidates: list[Path] = []
    if cli_path:
        candidates.append(Path(cli_path))

    env_path = os.getenv("SLICE_DATASET_PATH")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(DEFAULT_DATASET_CANDIDATES)
    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = "\n".join(f"- {candidate}" for candidate in candidates)
    raise FileNotFoundError(f"Aucun dataset slice trouvÃ©. Chemins vÃ©rifiÃ©s :\n{searched}")


def prepare_training_frame(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    missing_columns = [column for column in SLICE_FEATURES if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"Colonnes manquantes dans le dataset slice : {missing_columns}")
    if "slice Type" not in dataframe.columns:
        raise ValueError("La colonne cible 'slice Type' est absente du dataset.")

    prepared = dataframe[list(SLICE_FEATURES)].copy()
    prepared["Packet delay"] = prepared["Packet delay"].astype(float) / PACKET_DELAY_DIVISOR
    prepared["Packet Loss Rate"] = prepared["Packet Loss Rate"].astype(float)
    prepared["LTE/5g Category"] = prepared["LTE/5g Category"].astype(int)
    prepared["Smartphone"] = prepared["Smartphone"].astype(int)
    prepared["IoT Devices"] = prepared["IoT Devices"].astype(int)
    prepared["GBR"] = prepared["GBR"].astype(int)

    target = dataframe["slice Type"].astype(str).map(RAW_SLICE_TARGET_MAP)
    if target.isnull().any():
        unknown = sorted(dataframe.loc[target.isnull(), "slice Type"].astype(str).unique().tolist())
        raise ValueError(f"Valeurs slice Type non supportÃ©es : {unknown}")

    return prepared, target


def train_and_export(dataset_path: Path, output_dir: Path) -> None:
    dataframe = pd.read_csv(dataset_path)
    features_frame, target = prepare_training_frame(dataframe)

    x_train, x_test, y_train, y_test = train_test_split(
        features_frame,
        target,
        train_size=0.70,
        random_state=12,
        stratify=target,
    )

    label_encoder = LabelEncoder()
    y_train_encoded = label_encoder.fit_transform(y_train)
    y_test_encoded = label_encoder.transform(y_test)

    model = lgb.LGBMClassifier(
        objective="multiclass",
        num_class=len(label_encoder.classes_),
        n_estimators=40,
        learning_rate=0.08,
        num_leaves=31,
        n_jobs=1,
        random_state=12,
        verbose=-1,
    )
    model.fit(x_train, y_train_encoded)

    predicted_labels = model.predict(x_test)
    predicted_probabilities = model.predict_proba(x_test)

    accuracy = accuracy_score(y_test_encoded, predicted_labels)
    weighted_f1 = f1_score(y_test_encoded, predicted_labels, average="weighted", zero_division=0)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model_slice_lightgbm.json"
    metadata_path = output_dir / "metadata_slice_lightgbm.json"

    model_dump = model.booster_.dump_model()
    exported_model = {
        "model_name": "model_slice_lightgbm",
        "format": "lightgbm_booster_dump_v1",
        "source_notebook": "LightGBM_Only.ipynb",
        "source_dataset": str(dataset_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "objective": str(model_dump.get("objective", "multiclass")),
        "num_class": int(model_dump.get("num_class", len(label_encoder.classes_))),
        "num_tree_per_iteration": int(model_dump.get("num_tree_per_iteration", len(label_encoder.classes_))),
        "feature_names": list(SLICE_FEATURES),
        "tree_info": [
            {
                "tree_index": int(tree["tree_index"]),
                "class_index": int(tree["tree_index"] % int(model_dump.get("num_tree_per_iteration", len(label_encoder.classes_)))),
                "tree_structure": simplify_tree(tree["tree_structure"]),
            }
            for tree in model_dump.get("tree_info", [])
        ],
    }
    model_path.write_text(json.dumps(exported_model, indent=2, ensure_ascii=False), encoding="utf-8")

    metadata = {
        "model_name": "model_slice_lightgbm",
        "model_type": "lightgbm.booster_dump",
        "source_notebook": "LightGBM_Only.ipynb",
        "source_dataset": str(dataset_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "features": list(SLICE_FEATURES),
        "target": "slice_type_group",
        "classes": label_encoder.classes_.tolist(),
        "class_distribution": dict(Counter(target.tolist())),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "training_packet_delay_divisor": PACKET_DELAY_DIVISOR,
        "runtime_packet_delay_divisor": 1.0,
        "runtime_feature_mapping": RUNTIME_FEATURE_MAPPING,
        "feature_importances": {
            feature: int(importance)
            for feature, importance in zip(SLICE_FEATURES, model.feature_importances_)
        },
        "metrics": {
            "accuracy": round(float(accuracy), 4),
            "weighted_f1": round(float(weighted_f1), 4),
            "avg_confidence": round(
                float(sum(max(probabilities) for probabilities in predicted_probabilities) / len(predicted_probabilities)),
                4,
            ),
        },
        "notes": [
            "Notebook-aligned LightGBM multiclass slice classifier.",
            "Packet delay is divided by 5.0 during training so the notebook dataset stays compatible with the application latency scale.",
            "Raw labels 1/2/3 are mapped to canonical telecom classes eMBB/mMTC/URLLC.",
            "The runtime artifact is exported as a LightGBM tree dump so Docker inference does not depend on libgomp.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[slice-export] Artefacts gÃ©nÃ©rÃ©s avec succÃ¨s.")
    print(f"[slice-export] Dataset source : {dataset_path}")
    print(f"[slice-export] Accuracy test : {accuracy:.4f}")
    print(f"[slice-export] Weighted F1 test : {weighted_f1:.4f}")
    print(f"[slice-export] ModÃ¨le : {model_path}")
    print(f"[slice-export] Metadata : {metadata_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporte les artefacts du classifieur de slice LightGBM.")
    parser.add_argument("--dataset", help="Chemin vers le train_dataset.csv.", default=None)
    parser.add_argument("--output-dir", default="data/models/slice", help="Dossier de sortie des artefacts.")
    args = parser.parse_args()

    dataset_path = resolve_dataset_path(args.dataset)
    train_and_export(dataset_path=dataset_path, output_dir=Path(args.output_dir))


if __name__ == "__main__":
    main()
