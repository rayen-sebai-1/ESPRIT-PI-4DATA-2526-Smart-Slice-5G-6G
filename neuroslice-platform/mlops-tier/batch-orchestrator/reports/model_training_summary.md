# Model Training Summary

Generated at: `2026-05-06T19:48:32+00:00`
Registry updated at: `2026-05-06T19:48:29+00:00`

## Dataset Processed Status

| Model | Status | Path |
| --- | --- | --- |
| congestion_5g | processed | `data/processed/congestion_5g_processed.npz` |
| congestion_6g | processed | `data/processed/6g_processed.csv` |
| sla_5g | processed | `data/processed/sla_5g_processed.npz` |
| sla_6g | processed | `data/processed/sla_6g_processed.npz` |
| slice_type_5g | processed | `data/processed/slice_type_5g_processed.npz` |
| slice_type_6g | processed | `data/processed/slice_type_6g_processed.npz` |

## Latest Model Lifecycle Results

### congestion_5g (v4)

- Model family: `pytorch_lstm`
- Task type: `binary_classification`
- Created at: `2026-05-06T18:52:56+00:00`
- MLflow run ID: `1c991c6d831041e1949a9b80a0bc863a`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/1c991c6d831041e1949a9b80a0bc863a/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/1c991c6d831041e1949a9b80a0bc863a/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/1c991c6d831041e1949a9b80a0bc863a/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/1c991c6d831041e1949a9b80a0bc863a/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.2154 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.977175` |
| val_f1 | `0.345679` |
| val_precision | `0.215385` |
| val_recall | `0.875000` |
| val_roc_auc | `0.979131` |

### congestion_6g (v3)

- Model family: `pytorch_lstm`
- Task type: `regression_forecast`
- Created at: `2026-05-06T19:13:50+00:00`
- MLflow run ID: `d847dbee97a7443aafe452b9b23a0e11`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_6g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/d847dbee97a7443aafe452b9b23a0e11/artifacts/models/congestion_6g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/d847dbee97a7443aafe452b9b23a0e11/artifacts/onnx/congestion_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/d847dbee97a7443aafe452b9b23a0e11/artifacts/onnx/congestion_6g_fp16.onnx`
- Preprocessor URI: `n/a`
- ONNX export status: `success`
- Reason: val_mae=0.0531 meets the < 5.0 rule.

| Metric | Value |
| --- | --- |
| val_mae | `0.053072` |
| val_mape | `38.596950` |
| val_rmse | `0.064416` |

### sla_5g (v6)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-06T19:48:29+00:00`
- MLflow run ID: `afd30cbb8a204ae6b2fb6332e13c8457`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/afd30cbb8a204ae6b2fb6332e13c8457/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/afd30cbb8a204ae6b2fb6332e13c8457/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/afd30cbb8a204ae6b2fb6332e13c8457/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/afd30cbb8a204ae6b2fb6332e13c8457/artifacts/preprocessing/scaler_sla_5g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9901 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.942536` |
| val_f1 | `0.890630` |
| val_precision | `0.802825` |
| val_recall | `1.000000` |
| val_roc_auc | `0.990077` |

### sla_6g (v3)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-06T18:40:49+00:00`
- MLflow run ID: `0d665165afbb44a3a8c022aa9e54b8b8`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/0d665165afbb44a3a8c022aa9e54b8b8/artifacts/models/sla_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/0d665165afbb44a3a8c022aa9e54b8b8/artifacts/onnx/sla_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/0d665165afbb44a3a8c022aa9e54b8b8/artifacts/onnx/sla_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/0d665165afbb44a3a8c022aa9e54b8b8/artifacts/preprocessing/scaler_sla_6g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9736 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.888388` |
| val_f1 | `0.897941` |
| val_precision | `0.912558` |
| val_recall | `0.883784` |
| val_roc_auc | `0.973591` |

### slice_type_5g (v4)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-06T19:14:00+00:00`
- MLflow run ID: `a27364552d4d4d3ebec009848b8f12b8`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/a27364552d4d4d3ebec009848b8f12b8/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/a27364552d4d4d3ebec009848b8f12b8/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/a27364552d4d4d3ebec009848b8f12b8/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/a27364552d4d4d3ebec009848b8f12b8/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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

### slice_type_6g (v3)

- Model family: `xgboost_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-06T19:14:09+00:00`
- MLflow run ID: `be42c07aa36c4a918d43efc855b58ee0`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/be42c07aa36c4a918d43efc855b58ee0/artifacts/models/slice_type_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/be42c07aa36c4a918d43efc855b58ee0/artifacts/onnx/slice_type_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/be42c07aa36c4a918d43efc855b58ee0/artifacts/onnx/slice_type_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/be42c07aa36c4a918d43efc855b58ee0/artifacts/preprocessing/label_encoder_slice_type_6g.pkl`
- ONNX export status: `success`
- Reason: val_accuracy=1.0000 meets the >= 0.80 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `1.000000` |
| val_f1 | `1.000000` |
| val_f1_score | `1.000000` |
| val_precision | `1.000000` |
| val_recall | `1.000000` |

Warnings:
- Suspicious 100% validation accuracy detected; possible leakage.
