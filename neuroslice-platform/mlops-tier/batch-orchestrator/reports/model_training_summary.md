# Model Training Summary

Generated at: `2026-05-02T15:59:45+00:00`
Registry updated at: `2026-05-02T15:59:42+00:00`

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

### congestion_5g (v5)

- Model family: `pytorch_lstm`
- Task type: `binary_classification`
- Created at: `2026-05-02T15:59:42+00:00`
- MLflow run ID: `2b41917a43f4412fac9095e9be081000`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/2b41917a43f4412fac9095e9be081000/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/2b41917a43f4412fac9095e9be081000/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/2b41917a43f4412fac9095e9be081000/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/2b41917a43f4412fac9095e9be081000/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.1940 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.975452` |
| val_f1 | `0.313253` |
| val_precision | `0.194030` |
| val_recall | `0.812500` |
| val_roc_auc | `0.980675` |

### congestion_6g (v1)

- Model family: `pytorch_lstm`
- Task type: `regression_forecast`
- Created at: `2026-04-30T03:50:14+00:00`
- MLflow run ID: `2963d294f9c444adafa160dfda963d7b`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_6g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/2963d294f9c444adafa160dfda963d7b/artifacts/models/congestion_6g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/2963d294f9c444adafa160dfda963d7b/artifacts/onnx/congestion_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/2963d294f9c444adafa160dfda963d7b/artifacts/onnx/congestion_6g_fp16.onnx`
- Preprocessor URI: `n/a`
- ONNX export status: `success`
- Reason: val_mae=0.0496 meets the < 5.0 rule.

| Metric | Value |
| --- | --- |
| val_mae | `0.049576` |
| val_mape | `35.178834` |
| val_rmse | `0.060669` |

### sla_5g (v26)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-02T15:59:00+00:00`
- MLflow run ID: `64623bb4258b4359909796631152cd08`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/64623bb4258b4359909796631152cd08/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/64623bb4258b4359909796631152cd08/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/64623bb4258b4359909796631152cd08/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/64623bb4258b4359909796631152cd08/artifacts/preprocessing/scaler_sla_5g.pkl`
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
- Created at: `2026-05-01T22:43:29+00:00`
- MLflow run ID: `d610cd65b7a544628a2b4a6492b52d7d`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/d610cd65b7a544628a2b4a6492b52d7d/artifacts/models/sla_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/d610cd65b7a544628a2b4a6492b52d7d/artifacts/onnx/sla_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/d610cd65b7a544628a2b4a6492b52d7d/artifacts/onnx/sla_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/d610cd65b7a544628a2b4a6492b52d7d/artifacts/preprocessing/scaler_sla_6g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9736 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.888388` |
| val_f1 | `0.897941` |
| val_precision | `0.912558` |
| val_recall | `0.883784` |
| val_roc_auc | `0.973591` |

### slice_type_5g (v10)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-02T15:55:09+00:00`
- MLflow run ID: `804020fe4fb1439391704cd009dfdc34`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/804020fe4fb1439391704cd009dfdc34/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/804020fe4fb1439391704cd009dfdc34/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/804020fe4fb1439391704cd009dfdc34/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/804020fe4fb1439391704cd009dfdc34/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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
- Created at: `2026-04-30T03:50:34+00:00`
- MLflow run ID: `4ee0a3ed61874af689e438f4e27283b3`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/4ee0a3ed61874af689e438f4e27283b3/artifacts/models/slice_type_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/4ee0a3ed61874af689e438f4e27283b3/artifacts/onnx/slice_type_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/4ee0a3ed61874af689e438f4e27283b3/artifacts/onnx/slice_type_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/4ee0a3ed61874af689e438f4e27283b3/artifacts/preprocessing/label_encoder_slice_type_6g.pkl`
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
