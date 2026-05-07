# Model Training Summary

Generated at: `2026-05-07T12:23:53+00:00`
Registry updated at: `2026-05-07T12:23:49+00:00`

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

### congestion_5g (v2)

- Model family: `pytorch_lstm`
- Task type: `binary_classification`
- Created at: `2026-05-07T12:06:00+00:00`
- MLflow run ID: `e9e5bc8d8e5c4723a1d52fca56cdfd30`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/e9e5bc8d8e5c4723a1d52fca56cdfd30/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/e9e5bc8d8e5c4723a1d52fca56cdfd30/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/e9e5bc8d8e5c4723a1d52fca56cdfd30/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/e9e5bc8d8e5c4723a1d52fca56cdfd30/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.2647 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.986219` |
| val_f1 | `0.360000` |
| val_precision | `0.264706` |
| val_recall | `0.562500` |
| val_roc_auc | `0.982735` |

### congestion_6g (v2)

- Model family: `pytorch_lstm`
- Task type: `regression_forecast`
- Created at: `2026-05-07T12:23:22+00:00`
- MLflow run ID: `856c3c493a6844aca982d3498b094d15`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `staging`
- Promoted: `False`
- Promotion decision: `candidate`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_6g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/856c3c493a6844aca982d3498b094d15/artifacts/models/congestion_6g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/856c3c493a6844aca982d3498b094d15/artifacts/onnx/congestion_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/856c3c493a6844aca982d3498b094d15/artifacts/onnx/congestion_6g_fp16.onnx`
- Preprocessor URI: `n/a`
- ONNX export status: `success`
- Reason: val_mae=0.0772 meets the < 5.0 rule.

| Metric | Value |
| --- | --- |
| val_mae | `0.077210` |
| val_mape | `57.149933` |
| val_rmse | `0.090690` |

### sla_5g (v2)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-07T12:00:16+00:00`
- MLflow run ID: `0df7738d696540ff907dfa2f2e8a935f`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/0df7738d696540ff907dfa2f2e8a935f/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/0df7738d696540ff907dfa2f2e8a935f/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/0df7738d696540ff907dfa2f2e8a935f/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/0df7738d696540ff907dfa2f2e8a935f/artifacts/preprocessing/scaler_sla_5g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9901 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.942536` |
| val_f1 | `0.890630` |
| val_precision | `0.802825` |
| val_recall | `1.000000` |
| val_roc_auc | `0.990077` |

### sla_6g (v2)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-07T12:00:28+00:00`
- MLflow run ID: `cfa2a48f025f4459a5488c09e8d2cdac`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/cfa2a48f025f4459a5488c09e8d2cdac/artifacts/models/sla_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/cfa2a48f025f4459a5488c09e8d2cdac/artifacts/onnx/sla_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/cfa2a48f025f4459a5488c09e8d2cdac/artifacts/onnx/sla_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/cfa2a48f025f4459a5488c09e8d2cdac/artifacts/preprocessing/scaler_sla_6g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9736 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.888388` |
| val_f1 | `0.897941` |
| val_precision | `0.912558` |
| val_recall | `0.883784` |
| val_roc_auc | `0.973591` |

### slice_type_5g (v2)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-07T12:23:34+00:00`
- MLflow run ID: `e7dd65a85e6c4ba38fa72f118efe7dc7`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/e7dd65a85e6c4ba38fa72f118efe7dc7/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/e7dd65a85e6c4ba38fa72f118efe7dc7/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/e7dd65a85e6c4ba38fa72f118efe7dc7/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/e7dd65a85e6c4ba38fa72f118efe7dc7/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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

### slice_type_6g (v2)

- Model family: `xgboost_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-07T12:23:48+00:00`
- MLflow run ID: `6345138a6f094d3e84f89938db83cc37`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/6345138a6f094d3e84f89938db83cc37/artifacts/models/slice_type_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/6345138a6f094d3e84f89938db83cc37/artifacts/onnx/slice_type_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/6345138a6f094d3e84f89938db83cc37/artifacts/onnx/slice_type_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/6345138a6f094d3e84f89938db83cc37/artifacts/preprocessing/label_encoder_slice_type_6g.pkl`
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
