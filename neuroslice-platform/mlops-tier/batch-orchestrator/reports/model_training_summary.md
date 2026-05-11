# Model Training Summary

Generated at: `2026-05-10T16:09:54+00:00`
Registry updated at: `2026-05-10T16:09:51+00:00`

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
- Created at: `2026-05-10T15:46:27+00:00`
- MLflow run ID: `013ac14981c044febc7f1e6524660912`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/013ac14981c044febc7f1e6524660912/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/013ac14981c044febc7f1e6524660912/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/013ac14981c044febc7f1e6524660912/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/013ac14981c044febc7f1e6524660912/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.1429 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.965116` |
| val_f1 | `0.242991` |
| val_precision | `0.142857` |
| val_recall | `0.812500` |
| val_roc_auc | `0.972382` |

### congestion_6g (v1)

- Model family: `pytorch_lstm`
- Task type: `regression_forecast`
- Created at: `2026-05-10T16:09:22+00:00`
- MLflow run ID: `d0e090b8e8664aac82115699af576b8b`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_6g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/d0e090b8e8664aac82115699af576b8b/artifacts/models/congestion_6g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/d0e090b8e8664aac82115699af576b8b/artifacts/onnx/congestion_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/d0e090b8e8664aac82115699af576b8b/artifacts/onnx/congestion_6g_fp16.onnx`
- Preprocessor URI: `n/a`
- ONNX export status: `success`
- Reason: val_mae=0.0472 meets the < 5.0 rule.

| Metric | Value |
| --- | --- |
| val_mae | `0.047198` |
| val_mape | `33.972669` |
| val_rmse | `0.058163` |

### sla_5g (v1)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-10T15:37:19+00:00`
- MLflow run ID: `c449fafadf144a6c86ab2420183fd6da`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/c449fafadf144a6c86ab2420183fd6da/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/c449fafadf144a6c86ab2420183fd6da/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/c449fafadf144a6c86ab2420183fd6da/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/c449fafadf144a6c86ab2420183fd6da/artifacts/preprocessing/scaler_sla_5g.pkl`
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
- Created at: `2026-05-10T15:37:37+00:00`
- MLflow run ID: `09d5fc4ed0b54533a506a8d6dd9a09fb`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/09d5fc4ed0b54533a506a8d6dd9a09fb/artifacts/models/sla_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/09d5fc4ed0b54533a506a8d6dd9a09fb/artifacts/onnx/sla_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/09d5fc4ed0b54533a506a8d6dd9a09fb/artifacts/onnx/sla_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/09d5fc4ed0b54533a506a8d6dd9a09fb/artifacts/preprocessing/scaler_sla_6g.pkl`
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
- Created at: `2026-05-10T16:09:35+00:00`
- MLflow run ID: `2ba380674c1442f59286eaf8f8d2902d`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/2ba380674c1442f59286eaf8f8d2902d/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/2ba380674c1442f59286eaf8f8d2902d/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/2ba380674c1442f59286eaf8f8d2902d/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/2ba380674c1442f59286eaf8f8d2902d/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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
- Created at: `2026-05-10T16:09:50+00:00`
- MLflow run ID: `a51087dc2ff94228b2133775bd6ad8c1`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/a51087dc2ff94228b2133775bd6ad8c1/artifacts/models/slice_type_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/a51087dc2ff94228b2133775bd6ad8c1/artifacts/onnx/slice_type_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/a51087dc2ff94228b2133775bd6ad8c1/artifacts/onnx/slice_type_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/a51087dc2ff94228b2133775bd6ad8c1/artifacts/preprocessing/label_encoder_slice_type_6g.pkl`
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
