# Data Folder

This directory contains both the source datasets and the generated preprocessing artifacts used by the NeuroSlice MLOps project.

## Layout

- `data/raw/`: committed source CSV files
- `data/processed/`: generated processed datasets, scalers, encoders, and preprocessing artifacts

## Current Raw Datasets

Files currently present in `data/raw/`:

- `5G_prepared.csv`
- `6G_prepared.csv`
- `network_slicing_dataset_enriched_timeseries.csv`
- `network_slicing_dataset_v3.csv`
- `train_dataset.csv`
- `train_dataset_enriched_timeseries.csv`

## Current Processed Artifacts

Files currently present in `data/processed/` include:

- `6g_processed.csv`
- `congestion_5g_processed.npz`
- `sla_5g_processed.npz`
- `sla_6g_processed.npz`
- `slice_type_5g_processed.npz`
- `slice_type_6g_processed.npz`
- `preprocessor_congestion_5g.pkl`
- `scaler_sla_5g.pkl`
- `scaler_sla_6g.pkl`
- `encoders_sla_6g.pkl`
- `label_encoder_slice_type_5g.pkl`
- `label_encoder_slice_type_6g.pkl`

These generated artifacts are important in the current repository state because:

- the MLOps API loads several of them directly
- runtime AIOps services mount this directory through the integrated Compose stack
- the repository currently keeps these local artifacts alongside the codebase

## Regenerating Processed Data

From `mlops-tier/batch-orchestrator/`:

```bash
make data
make data-sla-5g
make data-sla-6g
make data-congestion-5g
make data-slice-type-5g
make data-slice-type-6g
```

Run the full data and training pipeline:

```bash
make pipeline
```

## Practical Note

Earlier documentation treated `data/processed/` as purely disposable output. In the current workspace, those artifacts are part of the local runtime contract and are intentionally present so the platform can run without first rebuilding every preprocessing step.
