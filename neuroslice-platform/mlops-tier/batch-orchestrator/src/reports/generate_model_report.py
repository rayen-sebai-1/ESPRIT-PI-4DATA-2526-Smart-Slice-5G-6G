"""Generate an offline markdown summary from the model registry."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.models.lifecycle import (
    REGISTRY_PATH,
    REPORT_PATH,
    dataset_status,
    latest_registry_entries,
    load_registry,
    utcnow_iso,
)


def generate_model_report(
    *,
    registry_path: Path = REGISTRY_PATH,
    output_path: Path = REPORT_PATH,
) -> Path:
    """Render a markdown report from the latest registry entries."""
    registry = load_registry(registry_path)
    latest_entries = latest_registry_entries(registry_path)

    lines: list[str] = [
        "# Model Training Summary",
        "",
        f"Generated at: `{utcnow_iso()}`",
        f"Registry updated at: `{registry.get('generated_at') or 'n/a'}`",
        "",
        "## Dataset Processed Status",
        "",
        "| Model | Status | Path |",
        "| --- | --- | --- |",
    ]

    for row in dataset_status():
        lines.append(f"| {row['model_name']} | {row['status']} | `{row['path']}` |")

    lines.extend(
        [
            "",
            "## Latest Model Lifecycle Results",
            "",
        ]
    )

    if not latest_entries:
        lines.append("No registry entries were found.")
    else:
        for entry in latest_entries:
            lines.extend(_render_entry(entry))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return output_path


def _render_entry(entry: dict) -> Iterable[str]:
    metrics = entry.get("metrics") or {}
    warnings = list(entry.get("warnings") or [])
    if entry.get("onnx_export_status") != "success":
        warnings.append(f"ONNX export failed: {entry.get('onnx_export_reason') or 'unknown reason'}")

    lines = [
        f"### {entry.get('model_name')} (v{entry.get('version')})",
        "",
        f"- Model family: `{entry.get('model_family')}`",
        f"- Created at: `{entry.get('created_at')}`",
        f"- MLflow run ID: `{entry.get('run_id') or 'n/a'}`",
        f"- Quality gate: `{entry.get('quality_gate_status')}`",
        f"- Promotion decision: `{entry.get('promotion_status')}`",
        f"- Artifact format: `{entry.get('artifact_format')}`",
        f"- Local artifact: `{entry.get('local_artifact_path') or 'n/a'}`",
        f"- MLflow artifact URI: `{entry.get('mlflow_artifact_uri') or 'n/a'}`",
        f"- ONNX FP16 artifact: `{entry.get('onnx_fp16_path') or 'n/a'}`",
        f"- ONNX export status: `{entry.get('onnx_export_status')}`",
        f"- Reason: {entry.get('reason') or 'n/a'}",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]

    for metric_name in sorted(metrics):
        lines.append(f"| {metric_name} | `{metrics[metric_name]:.6f}` |")

    if warnings:
        lines.extend(["", "Warnings:"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.append("")
    return lines


if __name__ == "__main__":
    report_path = generate_model_report()
    print(f"[INFO] Wrote model report to {report_path.as_posix()}")
