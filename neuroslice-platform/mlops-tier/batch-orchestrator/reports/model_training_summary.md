# Model Training Summary

Generated at: `2026-04-26T11:55:26+00:00`
Registry updated at: `2026-04-26T11:55:23+00:00`

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

### congestion_5g (v10)

- Model family: `pytorch_lstm`
- Task type: `binary_classification`
- Created at: `2026-04-26T11:55:01+00:00`
- MLflow run ID: `d1103be57cd140d6a10a5d343348919e`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/d1103be57cd140d6a10a5d343348919e/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/d1103be57cd140d6a10a5d343348919e/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/d1103be57cd140d6a10a5d343348919e/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/d1103be57cd140d6a10a5d343348919e/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.2034 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.978036` |
| val_f1 | `0.320000` |
| val_precision | `0.203390` |
| val_recall | `0.750000` |
| val_roc_auc | `0.983033` |

### sla_5g (v7)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-04-26T11:55:13+00:00`
- MLflow run ID: `c6fe46944e1e493fa1e7e0e8741709fb`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/c6fe46944e1e493fa1e7e0e8741709fb/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/c6fe46944e1e493fa1e7e0e8741709fb/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/c6fe46944e1e493fa1e7e0e8741709fb/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/c6fe46944e1e493fa1e7e0e8741709fb/artifacts/preprocessing/scaler_sla_5g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9901 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.942536` |
| val_f1 | `0.890630` |
| val_precision | `0.802825` |
| val_recall | `1.000000` |
| val_roc_auc | `0.990077` |

### slice_type_5g (v6)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-04-26T11:55:23+00:00`
- MLflow run ID: `3294028e6cd6464ca7fe972d9eeb5348`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/3294028e6cd6464ca7fe972d9eeb5348/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/3294028e6cd6464ca7fe972d9eeb5348/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/3294028e6cd6464ca7fe972d9eeb5348/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/3294028e6cd6464ca7fe972d9eeb5348/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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
