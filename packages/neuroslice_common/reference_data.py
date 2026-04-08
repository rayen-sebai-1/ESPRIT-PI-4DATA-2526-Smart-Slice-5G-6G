from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
import shutil

DEFAULT_DOWNLOAD_ROOT = Path(r"C:\Users\DELL\Downloads")
DEFAULT_DATASET_ROOT = DEFAULT_DOWNLOAD_ROOT / "PI Data-20260406T215523Z-3-001" / "PI Data" / "dataset 5G et 6G"
DEFAULT_PDF_PATH = (
    DEFAULT_DOWNLOAD_ROOT / "Projet 1 Network slicing" / "Projet 1 Network slicing" / "Project 1.pdf"
)


@dataclass(frozen=True, slots=True)
class ReferenceAsset:
    key: str
    source_path: Path
    target_relative_path: Path
    description: str
    asset_type: str


REFERENCE_ASSETS = (
    ReferenceAsset(
        key="sla_training",
        source_path=DEFAULT_DATASET_ROOT / "train_dataset.csv",
        target_relative_path=Path("raw") / "train_dataset.csv",
        description="Primary SLA and slice classification dataset.",
        asset_type="csv",
    ),
    ReferenceAsset(
        key="anomaly_misrouting",
        source_path=DEFAULT_DATASET_ROOT / "network_slicing_dataset - v3.csv",
        target_relative_path=Path("raw") / "network_slicing_dataset_v3.csv",
        description="Reference dataset for anomaly and misrouting detection.",
        asset_type="csv",
    ),
    ReferenceAsset(
        key="congestion_timeseries",
        source_path=DEFAULT_DATASET_ROOT / "network_slicing_dataset_enriched_timeseries.csv",
        target_relative_path=Path("raw") / "network_slicing_dataset_enriched_timeseries.csv",
        description="Reference time-series telemetry dataset for congestion forecasting.",
        asset_type="csv",
    ),
    ReferenceAsset(
        key="project_pdf",
        source_path=DEFAULT_PDF_PATH,
        target_relative_path=Path("reference") / "Project_1_Network_Slicing.pdf",
        description="Project explanatory PDF supplied by the user.",
        asset_type="pdf",
    ),
)


def infer_delimiter(path: Path) -> str:
    sample = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    return ";" if sample.count(";") > sample.count(",") else ","


def summarize_csv(path: Path) -> dict[str, object]:
    delimiter = infer_delimiter(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        header = next(reader)
        row_count = sum(1 for _ in reader)

    return {
        "delimiter": delimiter,
        "columns_count": len(header),
        "rows_count": row_count,
        "columns": header,
    }


def build_reference_manifest(data_root: Path) -> dict[str, object]:
    manifest_assets: list[dict[str, object]] = []
    for asset in REFERENCE_ASSETS:
        target_path = data_root / asset.target_relative_path
        payload = {
            "key": asset.key,
            "description": asset.description,
            "asset_type": asset.asset_type,
            "source_path": str(asset.source_path),
            "target_path": str(target_path),
            "exists": target_path.exists(),
        }
        if target_path.exists():
            payload["size_bytes"] = target_path.stat().st_size
            if asset.asset_type == "csv":
                payload.update(summarize_csv(target_path))
        manifest_assets.append(payload)

    return {
        "assets": manifest_assets,
        "dataset_root": str(DEFAULT_DATASET_ROOT),
        "pdf_source": str(DEFAULT_PDF_PATH),
    }


def import_reference_assets(data_root: Path) -> dict[str, object]:
    data_root.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, object]] = []

    for asset in REFERENCE_ASSETS:
        destination = data_root / asset.target_relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if asset.source_path.exists():
            shutil.copy2(asset.source_path, destination)
            copied.append(
                {
                    "key": asset.key,
                    "source_path": str(asset.source_path),
                    "target_path": str(destination),
                }
            )

    manifest = build_reference_manifest(data_root)
    manifest["copied"] = copied
    manifest_path = data_root / "reference_assets_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest
