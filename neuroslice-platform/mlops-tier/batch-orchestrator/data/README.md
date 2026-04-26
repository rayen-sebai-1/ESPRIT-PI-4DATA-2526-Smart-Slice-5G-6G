# Data Folder

This directory contains committed raw datasets for the NeuroSlice MLOps project and the generated preprocessing outputs used by training, promotion, and runtime services.

## Layout

- `data/raw/`: committed source CSV files
- `data/processed/`: generated preprocessing outputs created by Make targets and preprocessing scripts

## Raw Datasets

Files currently present in `data/raw/`:

- `5G_prepared.csv`
- `6G_prepared.csv`
- `network_slicing_dataset_enriched_timeseries.csv`
- `network_slicing_dataset_v3.csv`
- `train_dataset.csv`
- `train_dataset_enriched_timeseries.csv`

## Generated `data/processed/` Artifacts

Depending on which preprocessing targets run, this folder can contain:

- processed `.csv` and `.npz` datasets
- congestion preprocessors
- SLA scalers
- slice label encoders
- task-specific artifacts used by the prediction API and AIOps workers

Common runtime files:

- `preprocessor_congestion_5g.pkl`
- `scaler_sla_5g.pkl`
- `label_encoder_slice_type_5g.pkl`

These files are generated locally and should be treated as runtime artifacts.

## Regenerating Processed Data

From `mlops-tier/batch-orchestrator/`:

```bash
make data-sla-5g
make data-sla-6g
make data-congestion-5g
make data-slice-type-5g
make data-slice-type-6g
```

Run the default 5G pipeline:

```bash
make pipeline
```

Run the wider 5G/6G path:

```bash
make pipeline-all
```

## Runtime Note

AIOps services mount `batch-orchestrator/data` at `/mlops/data:ro`. Model inference can use generated preprocessors, scalers, and label encoders when they exist. If they are missing, services keep running and use service-specific fallback behavior.
