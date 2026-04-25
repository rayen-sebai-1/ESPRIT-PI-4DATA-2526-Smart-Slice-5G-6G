# Data Folder

This directory contains the committed raw datasets for the NeuroSlice MLOps project and the location where generated preprocessing outputs are created.

## Layout

- `data/raw/`: committed source CSV files
- `data/processed/`: generated preprocessing outputs created by the Make targets and preprocessing scripts

## Current Committed Files

Files currently present in `data/raw/`:

- `5G_prepared.csv`
- `6G_prepared.csv`
- `network_slicing_dataset_enriched_timeseries.csv`
- `network_slicing_dataset_v3.csv`
- `train_dataset.csv`
- `train_dataset_enriched_timeseries.csv`

In the current repository snapshot, `data/processed/` is not committed. Its contents are generated locally and ignored by git.

## What Gets Generated Under `data/processed/`

Depending on which preprocessing targets you run, this folder can contain:

- processed `.csv` and `.npz` datasets
- congestion preprocessors
- SLA scalers
- slice label encoders
- other task-specific preprocessing artifacts used by the prediction API and runtime workers

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

Runtime AIOps services mount `batch-orchestrator/data` directly. If you want them to use generated preprocessors instead of falling back to heuristics, you need to create the required `data/processed/` artifacts locally first.
