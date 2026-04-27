# Model Training Summary

Generated at: `2026-04-27T16:47:18+00:00`
Registry updated at: `2026-04-27T16:47:17+00:00`

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

### congestion_5g (v24)

- Model family: `pytorch_lstm`
- Task type: `binary_classification`
- Created at: `2026-04-27T16:47:00+00:00`
- MLflow run ID: `0cd614d6a7014af0bbd5bd5b4bc50569`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `onnx_fp16`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/0cd614d6a7014af0bbd5bd5b4bc50569/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `s3://mlflow-artifacts/1/0cd614d6a7014af0bbd5bd5b4bc50569/artifacts/onnx/congestion_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/0cd614d6a7014af0bbd5bd5b4bc50569/artifacts/onnx/congestion_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/0cd614d6a7014af0bbd5bd5b4bc50569/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `success`
- Reason: val_precision=0.2105 is below 0.50; congestion_5g is not auto-promoted on AUC alone.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.978898` |
| val_f1 | `0.328767` |
| val_precision | `0.210526` |
| val_recall | `0.750000` |
| val_roc_auc | `0.978697` |

### sla_5g (v13)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-04-27T16:47:08+00:00`
- MLflow run ID: `d26447906369412fb39aa6a47f52b7ff`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/d26447906369412fb39aa6a47f52b7ff/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `s3://mlflow-artifacts/1/d26447906369412fb39aa6a47f52b7ff/artifacts/onnx/sla_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/d26447906369412fb39aa6a47f52b7ff/artifacts/onnx/sla_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/d26447906369412fb39aa6a47f52b7ff/artifacts/preprocessing/scaler_sla_5g.pkl`
- ONNX export status: `success`
- Reason: val_roc_auc=0.9901 meets the >= 0.75 rule.

| Metric | Value |
| --- | --- |
| val_accuracy | `0.942536` |
| val_f1 | `0.890630` |
| val_precision | `0.802825` |
| val_recall | `1.000000` |
| val_roc_auc | `0.990077` |

### slice_type_5g (v12)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-04-27T16:47:16+00:00`
- MLflow run ID: `62a77a75d9084f0485850dbae8d1aa52`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `onnx_fp16`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/62a77a75d9084f0485850dbae8d1aa52/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `s3://mlflow-artifacts/1/62a77a75d9084f0485850dbae8d1aa52/artifacts/onnx/slice_type_5g.onnx`
- ONNX FP16 artifact: `s3://mlflow-artifacts/1/62a77a75d9084f0485850dbae8d1aa52/artifacts/onnx/slice_type_5g_fp16.onnx`
- Preprocessor URI: `s3://mlflow-artifacts/1/62a77a75d9084f0485850dbae8d1aa52/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
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
