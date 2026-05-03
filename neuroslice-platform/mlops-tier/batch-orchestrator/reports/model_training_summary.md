# Model Training Summary

Generated at: `2026-05-03T03:49:27+00:00`
Registry updated at: `2026-05-03T03:49:25+00:00`

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

### congestion_5g (v6)

- Model family: `pytorch_lstm`
- Task type: `binary_classification`
- Created at: `2026-05-03T00:17:51+00:00`
- MLflow run ID: `a7e1cca21d6e46f183cdb2a4ce6230cf`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/a7e1cca21d6e46f183cdb2a4ce6230cf/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/a7e1cca21d6e46f183cdb2a4ce6230cf/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/a7e1cca21d6e46f183cdb2a4ce6230cf/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/a7e1cca21d6e46f183cdb2a4ce6230cf/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.1538 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.965978` |
| val_f1 | `0.261682` |
| val_precision | `0.153846` |
| val_recall | `0.875000` |
| val_roc_auc | `0.976556` |

### congestion_6g (v2)

- Model family: `pytorch_lstm`
- Task type: `regression_forecast`
- Created at: `2026-05-03T00:19:58+00:00`
- MLflow run ID: `c4058187fcda469d9395da46d40e51e8`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_6g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/c4058187fcda469d9395da46d40e51e8/artifacts/models/congestion_6g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/c4058187fcda469d9395da46d40e51e8/artifacts/onnx/congestion_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/c4058187fcda469d9395da46d40e51e8/artifacts/onnx/congestion_6g_fp16.onnx`
- Preprocessor URI: `n/a`
- ONNX export status: `success`
- Reason: val_mae=0.0390 meets the < 5.0 rule.

| Metric | Value |
| --- | --- |
| val_mae | `0.038969` |
| val_mape | `26.322996` |
| val_rmse | `0.048941` |

### sla_5g (v27)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-05-03T00:16:54+00:00`
- MLflow run ID: `3d1d99e460dc4c72b5eb0d69dd32ba24`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/3d1d99e460dc4c72b5eb0d69dd32ba24/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/3d1d99e460dc4c72b5eb0d69dd32ba24/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/3d1d99e460dc4c72b5eb0d69dd32ba24/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/3d1d99e460dc4c72b5eb0d69dd32ba24/artifacts/preprocessing/scaler_sla_5g.pkl`
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
- Created at: `2026-05-03T00:17:05+00:00`
- MLflow run ID: `d990a698788f429f835abbedb9ee69ba`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/d990a698788f429f835abbedb9ee69ba/artifacts/models/sla_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/d990a698788f429f835abbedb9ee69ba/artifacts/onnx/sla_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/d990a698788f429f835abbedb9ee69ba/artifacts/onnx/sla_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/d990a698788f429f835abbedb9ee69ba/artifacts/preprocessing/scaler_sla_6g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9736 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.888388` |
| val_f1 | `0.897941` |
| val_precision | `0.912558` |
| val_recall | `0.883784` |
| val_roc_auc | `0.973591` |

### slice_type_5g (v13)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-05-03T03:49:24+00:00`
- MLflow run ID: `64eca09f528646d6b92f5093a1cf7038`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/64eca09f528646d6b92f5093a1cf7038/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/64eca09f528646d6b92f5093a1cf7038/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/64eca09f528646d6b92f5093a1cf7038/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/64eca09f528646d6b92f5093a1cf7038/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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
- Created at: `2026-05-03T00:20:17+00:00`
- MLflow run ID: `45746424750f4269a6dbd7363ce09cd9`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/45746424750f4269a6dbd7363ce09cd9/artifacts/models/slice_type_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/45746424750f4269a6dbd7363ce09cd9/artifacts/onnx/slice_type_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/45746424750f4269a6dbd7363ce09cd9/artifacts/onnx/slice_type_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/45746424750f4269a6dbd7363ce09cd9/artifacts/preprocessing/label_encoder_slice_type_6g.pkl`
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
