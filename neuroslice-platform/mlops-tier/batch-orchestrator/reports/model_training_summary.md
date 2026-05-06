# Model Training Summary

Generated at: `2026-05-06T16:59:27+00:00`
Registry updated at: `2026-05-06T16:59:25+00:00`

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
- Created at: `2026-05-06T16:55:11+00:00`
- MLflow run ID: `0f8552e47ef14ce99af7aabbea7c4b26`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/0f8552e47ef14ce99af7aabbea7c4b26/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/0f8552e47ef14ce99af7aabbea7c4b26/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/0f8552e47ef14ce99af7aabbea7c4b26/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/0f8552e47ef14ce99af7aabbea7c4b26/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.1915 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.980620` |
| val_f1 | `0.285714` |
| val_precision | `0.191489` |
| val_recall | `0.562500` |
| val_roc_auc | `0.974008` |

### congestion_6g (v4)

- Model family: `pytorch_lstm`
- Task type: `regression_forecast`
- Created at: `2026-05-06T16:58:16+00:00`
- MLflow run ID: `231d25781b8846f783604d00cca6ccfd`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `staging`
- Promoted: `False`
- Promotion decision: `candidate`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_6g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/231d25781b8846f783604d00cca6ccfd/artifacts/models/congestion_6g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/231d25781b8846f783604d00cca6ccfd/artifacts/onnx/congestion_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/231d25781b8846f783604d00cca6ccfd/artifacts/onnx/congestion_6g_fp16.onnx`
- Preprocessor URI: `n/a`
- ONNX export status: `success`
- Reason: val_mae=0.0546 meets the < 5.0 rule.

| Metric | Value |
| --- | --- |
| val_mae | `0.054639` |
| val_mape | `41.516294` |
| val_rmse | `0.067465` |

### sla_5g (v6)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-06T16:53:49+00:00`
- MLflow run ID: `8041df5bdb2146ba9e8458d7773704bf`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/8041df5bdb2146ba9e8458d7773704bf/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/8041df5bdb2146ba9e8458d7773704bf/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/8041df5bdb2146ba9e8458d7773704bf/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/8041df5bdb2146ba9e8458d7773704bf/artifacts/preprocessing/scaler_sla_5g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9901 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.942536` |
| val_f1 | `0.890630` |
| val_precision | `0.802825` |
| val_recall | `1.000000` |
| val_roc_auc | `0.990077` |

### sla_6g (v5)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-06T16:54:05+00:00`
- MLflow run ID: `75dd472fe60543f19fc22af4de5e00c3`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/75dd472fe60543f19fc22af4de5e00c3/artifacts/models/sla_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/75dd472fe60543f19fc22af4de5e00c3/artifacts/onnx/sla_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/75dd472fe60543f19fc22af4de5e00c3/artifacts/onnx/sla_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/75dd472fe60543f19fc22af4de5e00c3/artifacts/preprocessing/scaler_sla_6g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9736 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.888388` |
| val_f1 | `0.897941` |
| val_precision | `0.912558` |
| val_recall | `0.883784` |
| val_roc_auc | `0.973591` |

### slice_type_5g (v5)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-06T16:58:30+00:00`
- MLflow run ID: `f6b18d49bab042c0bdaa06ce5e7410ff`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/f6b18d49bab042c0bdaa06ce5e7410ff/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/f6b18d49bab042c0bdaa06ce5e7410ff/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/f6b18d49bab042c0bdaa06ce5e7410ff/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/f6b18d49bab042c0bdaa06ce5e7410ff/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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

### slice_type_6g (v4)

- Model family: `xgboost_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-06T16:59:24+00:00`
- MLflow run ID: `9ea40f7a278d4119bc0ba54bdb2acbd0`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/9ea40f7a278d4119bc0ba54bdb2acbd0/artifacts/models/slice_type_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/9ea40f7a278d4119bc0ba54bdb2acbd0/artifacts/onnx/slice_type_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/9ea40f7a278d4119bc0ba54bdb2acbd0/artifacts/onnx/slice_type_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/9ea40f7a278d4119bc0ba54bdb2acbd0/artifacts/preprocessing/label_encoder_slice_type_6g.pkl`
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
