from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROMOTION_CODE = ROOT / "mlops-tier" / "batch-orchestrator" / "src" / "mlops" / "promotion.py"
DRIFT_REFERENCE_CODE = ROOT / "mlops-tier" / "batch-orchestrator" / "src" / "mlops" / "drift_reference.py"
MLOPS_README = ROOT / "mlops-tier" / "README.md"
BATCH_README = ROOT / "mlops-tier" / "batch-orchestrator" / "README.md"


def test_promotion_artifact_contract_paths_exist_in_source() -> None:
    promotion_text = PROMOTION_CODE.read_text(encoding="utf-8")
    drift_ref_text = DRIFT_REFERENCE_CODE.read_text(encoding="utf-8")
    combined = promotion_text + "\n" + drift_ref_text
    assert "model_fp16.onnx" in combined
    assert "metadata.json" in combined
    assert "version.txt" in combined
    assert "drift_reference.npz" in combined
    assert "drift_feature_schema.json" in combined


def test_mlops_registry_fields_are_documented() -> None:
    docs = (MLOPS_README.read_text(encoding="utf-8") + "\n" + BATCH_README.read_text(encoding="utf-8")).lower()
    required_field_terms = [
        "model_name",
        "version",
        "run_id",
        "framework",
        "metrics",
        "deployment_version",
    ]
    missing = [term for term in required_field_terms if term not in docs]
    assert not missing, f"Registry field terms missing from MLOps docs: {missing}"
