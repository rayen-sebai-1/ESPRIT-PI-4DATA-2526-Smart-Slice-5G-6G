# Model Training Summary

Generated at: `2026-05-07T11:09:20+00:00`
Registry updated at: `2026-05-07T11:09:17+00:00`

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

### congestion_5g (v1)

- Model family: `pytorch_lstm`
- Task type: `binary_classification`
- Created at: `2026-05-07T10:49:13+00:00`
- MLflow run ID: `e5e5adcc6105427abc1efce13bb6b80e`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/e5e5adcc6105427abc1efce13bb6b80e/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/e5e5adcc6105427abc1efce13bb6b80e/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/e5e5adcc6105427abc1efce13bb6b80e/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/e5e5adcc6105427abc1efce13bb6b80e/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.1778 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.980620` |
| val_f1 | `0.262295` |
| val_precision | `0.177778` |
| val_recall | `0.500000` |
| val_roc_auc | `0.974333` |

### congestion_6g (v1)

- Model family: `pytorch_lstm`
- Task type: `regression_forecast`
- Created at: `2026-05-07T11:08:52+00:00`
- MLflow run ID: `81b19d985e3945a98ee5369dea638882`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_6g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/81b19d985e3945a98ee5369dea638882/artifacts/models/congestion_6g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/81b19d985e3945a98ee5369dea638882/artifacts/onnx/congestion_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/81b19d985e3945a98ee5369dea638882/artifacts/onnx/congestion_6g_fp16.onnx`
- Preprocessor URI: `n/a`
- ONNX export status: `success`
- Reason: val_mae=0.0707 meets the < 5.0 rule.

| Metric | Value |
| --- | --- |
| val_mae | `0.070733` |
| val_mape | `54.616116` |
| val_rmse | `0.088347` |

### sla_5g (v1)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-07T10:43:52+00:00`
- MLflow run ID: `5660e7500adb4eaf8c46e2c5d68e9dcd`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/5660e7500adb4eaf8c46e2c5d68e9dcd/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/5660e7500adb4eaf8c46e2c5d68e9dcd/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/5660e7500adb4eaf8c46e2c5d68e9dcd/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/5660e7500adb4eaf8c46e2c5d68e9dcd/artifacts/preprocessing/scaler_sla_5g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9901 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.942536` |
| val_f1 | `0.890630` |
| val_precision | `0.802825` |
| val_recall | `1.000000` |
| val_roc_auc | `0.990077` |

### sla_6g (v1)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-07T10:44:05+00:00`
- MLflow run ID: `aeced0b81dbe48919905448bccb62021`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/aeced0b81dbe48919905448bccb62021/artifacts/models/sla_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/aeced0b81dbe48919905448bccb62021/artifacts/onnx/sla_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/aeced0b81dbe48919905448bccb62021/artifacts/onnx/sla_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/aeced0b81dbe48919905448bccb62021/artifacts/preprocessing/scaler_sla_6g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9736 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.888388` |
| val_f1 | `0.897941` |
| val_precision | `0.912558` |
| val_recall | `0.883784` |
| val_roc_auc | `0.973591` |

### slice_type_5g (v1)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-07T11:09:04+00:00`
- MLflow run ID: `23bb4c8d09aa4371bb1c5f82705dc262`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/23bb4c8d09aa4371bb1c5f82705dc262/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/23bb4c8d09aa4371bb1c5f82705dc262/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/23bb4c8d09aa4371bb1c5f82705dc262/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/23bb4c8d09aa4371bb1c5f82705dc262/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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

### slice_type_6g (v1)

- Model family: `xgboost_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-07T11:09:17+00:00`
- MLflow run ID: `5034247fd78945cd87d0e0bc874312ad`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/5034247fd78945cd87d0e0bc874312ad/artifacts/models/slice_type_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/5034247fd78945cd87d0e0bc874312ad/artifacts/onnx/slice_type_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/5034247fd78945cd87d0e0bc874312ad/artifacts/onnx/slice_type_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/5034247fd78945cd87d0e0bc874312ad/artifacts/preprocessing/label_encoder_slice_type_6g.pkl`
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
