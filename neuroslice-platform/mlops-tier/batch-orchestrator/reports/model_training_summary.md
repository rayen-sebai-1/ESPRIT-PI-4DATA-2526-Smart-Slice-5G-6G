# Model Training Summary

Generated at: `2026-04-28T12:22:50+00:00`
Registry updated at: `2026-04-28T12:22:49+00:00`

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
- Created at: `2026-04-28T12:21:08+00:00`
- MLflow run ID: `14dd763c5750436680ff4b595c2195b3`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/14dd763c5750436680ff4b595c2195b3/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/14dd763c5750436680ff4b595c2195b3/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/14dd763c5750436680ff4b595c2195b3/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/14dd763c5750436680ff4b595c2195b3/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.2093 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.982343` |
| val_f1 | `0.305085` |
| val_precision | `0.209302` |
| val_recall | `0.562500` |
| val_roc_auc | `0.976258` |

### congestion_6g (v2)

- Model family: `pytorch_lstm`
- Task type: `regression_forecast`
- Created at: `2026-04-28T12:22:32+00:00`
- MLflow run ID: `331a98f95bd34209a367cf61719c8ad8`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `staging`
- Promoted: `False`
- Promotion decision: `candidate`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_6g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/331a98f95bd34209a367cf61719c8ad8/artifacts/models/congestion_6g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/331a98f95bd34209a367cf61719c8ad8/artifacts/onnx/congestion_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/331a98f95bd34209a367cf61719c8ad8/artifacts/onnx/congestion_6g_fp16.onnx`
- Preprocessor URI: `n/a`
- ONNX export status: `success`
- Reason: val_mae=0.1306 meets the < 5.0 rule.

| Metric | Value |
| --- | --- |
| val_mae | `0.130622` |
| val_mape | `93.138525` |
| val_rmse | `0.146765` |

### sla_5g (v3)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-04-28T12:20:25+00:00`
- MLflow run ID: `40baa10a79d64b6d8575df85f91443f8`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/40baa10a79d64b6d8575df85f91443f8/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/40baa10a79d64b6d8575df85f91443f8/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/40baa10a79d64b6d8575df85f91443f8/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/40baa10a79d64b6d8575df85f91443f8/artifacts/preprocessing/scaler_sla_5g.pkl`
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
- Created at: `2026-04-28T12:20:31+00:00`
- MLflow run ID: `daf260a40d4e4be594a587fccd4dcd11`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/daf260a40d4e4be594a587fccd4dcd11/artifacts/models/sla_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/daf260a40d4e4be594a587fccd4dcd11/artifacts/onnx/sla_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/daf260a40d4e4be594a587fccd4dcd11/artifacts/onnx/sla_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/daf260a40d4e4be594a587fccd4dcd11/artifacts/preprocessing/scaler_sla_6g.pkl`
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
- Created at: `2026-04-28T12:22:40+00:00`
- MLflow run ID: `bd1fee5a52b3459a821154d026a49c1f`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/bd1fee5a52b3459a821154d026a49c1f/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/bd1fee5a52b3459a821154d026a49c1f/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/bd1fee5a52b3459a821154d026a49c1f/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/bd1fee5a52b3459a821154d026a49c1f/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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
- Created at: `2026-04-28T12:22:48+00:00`
- MLflow run ID: `8e19679eb47c43a4bf7df6538cfb324a`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_6g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/8e19679eb47c43a4bf7df6538cfb324a/artifacts/models/slice_type_6g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/8e19679eb47c43a4bf7df6538cfb324a/artifacts/onnx/slice_type_6g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/8e19679eb47c43a4bf7df6538cfb324a/artifacts/onnx/slice_type_6g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/8e19679eb47c43a4bf7df6538cfb324a/artifacts/preprocessing/label_encoder_slice_type_6g.pkl`
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
