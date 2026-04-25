# Model Training Summary

Generated at: `2026-04-25T23:02:48+00:00`
Registry updated at: `2026-04-25T23:02:46+00:00`

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

### congestion_5g (v5)

- Model family: `pytorch_lstm`
- Task type: `binary_classification`
- Created at: `2026-04-25T23:02:27+00:00`
- MLflow run ID: `ab45c10534a641bc91240ec08f97a9cc`
- Experiment: `neuroslice-aiops`
- Quality gate: `fail`
- Stage: `rejected`
- Promoted: `False`
- Promotion decision: `rejected`
- Artifact format: `torchscript`
- Local artifact: `congestion_5g_lstm_traced.pt`
- Artifact URI: `s3://mlflow-artifacts/1/ab45c10534a641bc91240ec08f97a9cc/artifacts/models/congestion_5g_lstm_traced.pt`
- ONNX artifact URI: `n/a`
- ONNX FP16 artifact: `n/a`
- Preprocessor URI: `s3://mlflow-artifacts/1/ab45c10534a641bc91240ec08f97a9cc/artifacts/preprocessing/preprocessor_congestion_5g.pkl`
- ONNX export status: `failed`
- Reason: val_precision=0.2364 is below 0.50; congestion_5g is not auto-promoted on AUC alone. ONNX export failed: Failed to export the model with torch.export. [96mThis is step 1/3[0m of exporting the model to ONNX. Next steps:
- Modify the model code for `torch.export.export` to succeed. Refer to https://pytorch.org/docs/stable/generated/exportdb/index.html for more information.
- Debug `torch.export.export` and submit a PR to PyTorch.
- Create an issue in the PyTorch GitHub repository against the [96m*torch.export*[0m component and attach the full error stack as well as reproduction scripts.

## Exception summary

<class 'ValueError'>: Found the following conflicts between user-specified ranges and inferred ranges from model tracing:
- Received user-specified dim hint Dim.DYNAMIC(min=None, max=None), but tracing inferred a static shape of 30 for dimension inputs['x'].shape[1].

(Refer to the full stack trace above for more information.)

| Metric | Value |
| --- | --- |
| val_accuracy | `0.980620` |
| val_f1 | `0.366197` |
| val_precision | `0.236364` |
| val_recall | `0.812500` |
| val_roc_auc | `0.982546` |

Warnings:
- ONNX export failed: Failed to export the model with torch.export. [96mThis is step 1/3[0m of exporting the model to ONNX. Next steps:
- Modify the model code for `torch.export.export` to succeed. Refer to https://pytorch.org/docs/stable/generated/exportdb/index.html for more information.
- Debug `torch.export.export` and submit a PR to PyTorch.
- Create an issue in the PyTorch GitHub repository against the [96m*torch.export*[0m component and attach the full error stack as well as reproduction scripts.

## Exception summary

<class 'ValueError'>: Found the following conflicts between user-specified ranges and inferred ranges from model tracing:
- Received user-specified dim hint Dim.DYNAMIC(min=None, max=None), but tracing inferred a static shape of 30 for dimension inputs['x'].shape[1].

(Refer to the full stack trace above for more information.)

### sla_5g (v2)

- Model family: `xgboost_classifier`
- Task type: `binary_classification`
- Created at: `2026-04-25T23:02:36+00:00`
- MLflow run ID: `e8a7736ade52485ea5f7a68dcb706642`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `xgboost_ubj`
- Local artifact: `sla_5g_model.ubj`
- Artifact URI: `s3://mlflow-artifacts/1/e8a7736ade52485ea5f7a68dcb706642/artifacts/models/sla_5g_model.ubj`
- ONNX artifact URI: `n/a`
- ONNX FP16 artifact: `n/a`
- Preprocessor URI: `s3://mlflow-artifacts/1/e8a7736ade52485ea5f7a68dcb706642/artifacts/preprocessing/scaler_sla_5g.pkl`
- ONNX export status: `failed`
- Reason: val_roc_auc=0.9901 meets the >= 0.75 rule. ONNX export failed: Operator XGBClassifier (type: XGBClassifier) got an input input with a wrong type <class 'skl2onnx.common.data_types.FloatTensorType'>. Only [<class 'onnxmltools.convert.common.data_types.FloatTensorType'>, <class 'onnxmltools.convert.common.data_types.Int64TensorType'>] are allowed

| Metric | Value |
| --- | --- |
| val_accuracy | `0.942536` |
| val_f1 | `0.890630` |
| val_precision | `0.802825` |
| val_recall | `1.000000` |
| val_roc_auc | `0.990077` |

Warnings:
- ONNX export failed: Operator XGBClassifier (type: XGBClassifier) got an input input with a wrong type <class 'skl2onnx.common.data_types.FloatTensorType'>. Only [<class 'onnxmltools.convert.common.data_types.FloatTensorType'>, <class 'onnxmltools.convert.common.data_types.Int64TensorType'>] are allowed

### slice_type_5g (v1)

- Model family: `lightgbm_classifier`
- Task type: `multiclass_classification`
- Created at: `2026-04-25T23:02:46+00:00`
- MLflow run ID: `70548d8ddfda4ee294e8c6419ee787fb`
- Experiment: `neuroslice-aiops`
- Quality gate: `pass`
- Stage: `production`
- Promoted: `True`
- Promotion decision: `promoted`
- Artifact format: `lightgbm_joblib`
- Local artifact: `slice_type_5g_model.pkl`
- Artifact URI: `s3://mlflow-artifacts/1/70548d8ddfda4ee294e8c6419ee787fb/artifacts/models/slice_type_5g_model.pkl`
- ONNX artifact URI: `n/a`
- ONNX FP16 artifact: `n/a`
- Preprocessor URI: `s3://mlflow-artifacts/1/70548d8ddfda4ee294e8c6419ee787fb/artifacts/preprocessing/label_encoder_slice_type_5g.pkl`
- ONNX export status: `failed`
- Reason: val_accuracy=0.8926 meets the >= 0.80 rule. ONNX export failed: Operator LgbmClassifier (type: LgbmClassifier) got an input input with a wrong type <class 'skl2onnx.common.data_types.FloatTensorType'>. Only [<class 'onnxmltools.convert.common.data_types.FloatTensorType'>, <class 'onnxmltools.convert.common.data_types.Int64TensorType'>] are allowed

| Metric | Value |
| --- | --- |
| val_accuracy | `0.892559` |
| val_f1 | `0.881478` |
| val_f1_class_1 | `0.908272` |
| val_f1_class_2 | `0.701991` |
| val_f1_class_3 | `1.000000` |
| val_precision | `0.910614` |
| val_recall | `0.892559` |

Warnings:
- ONNX export failed: Operator LgbmClassifier (type: LgbmClassifier) got an input input with a wrong type <class 'skl2onnx.common.data_types.FloatTensorType'>. Only [<class 'onnxmltools.convert.common.data_types.FloatTensorType'>, <class 'onnxmltools.convert.common.data_types.Int64TensorType'>] are allowed
