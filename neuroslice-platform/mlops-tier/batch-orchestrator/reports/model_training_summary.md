# Model Training Summary

Generated at: `2026-05-06T11:11:40+00:00`
Registry updated at: `2026-05-06T11:11:36+00:00`

## Dataset Processed Status

| Model | Status | Path |
| --- | --- | --- |
| congestion_5g | missing | `data/processed/congestion_5g_processed.npz` |
| congestion_6g | missing | `data/processed/6g_processed.csv` |
| sla_5g | processed | `data/processed/sla_5g_processed.npz` |
| sla_6g | missing | `data/processed/sla_6g_processed.npz` |
| slice_type_5g | missing | `data/processed/slice_type_5g_processed.npz` |
| slice_type_6g | missing | `data/processed/slice_type_6g_processed.npz` |

## Latest Model Lifecycle Results

### sla_5g (v1)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-06T11:11:35+00:00`
- MLflow run ID: `91ca987d8ee149d8908f735f1e5c8e0c`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/91ca987d8ee149d8908f735f1e5c8e0c/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/91ca987d8ee149d8908f735f1e5c8e0c/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/91ca987d8ee149d8908f735f1e5c8e0c/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/91ca987d8ee149d8908f735f1e5c8e0c/artifacts/preprocessing/scaler_sla_5g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9901 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.942536` |
| val_f1 | `0.890630` |
| val_precision | `0.802825` |
| val_recall | `1.000000` |
| val_roc_auc | `0.990077` |
