# Model Training Summary

Generated at: `2026-04-27T13:30:03+00:00`
Registry updated at: `2026-04-27T13:30:01+00:00`

## Dataset Processed Status

| Model | Status | Path |
| --- | --- | --- |
| congestion_5g | processed | `data/processed/congestion_5g_processed.npz` |
| congestion_6g | missing | `data/processed/6g_processed.csv` |
| sla_5g | processed | `data/processed/sla_5g_processed.npz` |
| sla_6g | missing | `data/processed/sla_6g_processed.npz` |
| slice_type_5g | processed | `data/processed/slice_type_5g_processed.npz` |
| slice_type_6g | missing | `data/processed/slice_type_6g_processed.npz` |

## Latest Model Lifecycle Results

### congestion_5g (v22)

- Model family: `pytorch_lstm`
- Task type: `binary_classification`
- Created at: `2026-04-27T13:29:44+00:00`
- MLflow run ID: `fe65166eed0f45f4946dc5b361c19433`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/fe65166eed0f45f4946dc5b361c19433/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/fe65166eed0f45f4946dc5b361c19433/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/fe65166eed0f45f4946dc5b361c19433/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/fe65166eed0f45f4946dc5b361c19433/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.1757 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.972438` |
| val_f1 | `0.288889` |
| val_precision | `0.175676` |
| val_recall | `0.812500` |
| val_roc_auc | `0.976718` |

### sla_5g (v11)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-04-27T13:29:53+00:00`
- MLflow run ID: `bc5f9fe293b347c0824952f9e8d05218`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/bc5f9fe293b347c0824952f9e8d05218/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/bc5f9fe293b347c0824952f9e8d05218/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/bc5f9fe293b347c0824952f9e8d05218/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/bc5f9fe293b347c0824952f9e8d05218/artifacts/preprocessing/scaler_sla_5g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9901 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.942536` |
| val_f1 | `0.890630` |
| val_precision | `0.802825` |
| val_recall | `1.000000` |
| val_roc_auc | `0.990077` |

### slice_type_5g (v10)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-04-27T13:30:01+00:00`
- MLflow run ID: `fc682663532a4c5b80357ac07546c30a`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/fc682663532a4c5b80357ac07546c30a/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/fc682663532a4c5b80357ac07546c30a/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/fc682663532a4c5b80357ac07546c30a/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/fc682663532a4c5b80357ac07546c30a/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
- ONNX export status: `success`
- Reason: val_accuracy=0.8926 meets the >= 0.80 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.892559` |
| val_f1 | `0.881478` |
| val_f1_class_1 | `0.908272` |
| val_f1_class_2 | `0.701991` |
| val_f1_class_3 | `1.000000` |
| val_precision | `0.910614` |
| val_recall | `0.892559` |
