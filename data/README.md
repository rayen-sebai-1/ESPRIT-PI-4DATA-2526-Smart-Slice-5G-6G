# Data Folder

All raw CSV datasets now live in **`data/raw/`**.

## `data/raw/` — canonical location

| File | Used by |
|------|---------|
| `network_slicing_dataset_enriched_timeseries.csv` | **LSTM congestion model** (`src/data/preprocess_6g.py`) |
| `5G_prepared.csv` | 5G slice-selection notebook / future training scripts |
| `6G_prepared.csv` | 6G slice-selection notebook / future training scripts |
| `network_slicing_dataset_v3.csv` | Exploratory notebooks |

## `data/processed/` — generated outputs

Processed CSVs are written here by the preprocessing scripts (e.g. `6g_processed.csv`).
Do **not** commit files in this folder.

## Notes

- The CSV files that previously lived directly in `data/` are **no longer needed** there.
  You can safely delete:
  - `data/5G_prepared.csv`
  - `data/6G_prepared.csv`
  - `data/network_slicing_dataset - v3.csv`
  - `data/network_slicing_dataset_enriched_timeseries.csv`
- Keep this `README.md` in the repository.
- All dataset files are listed in `.gitignore` and will not be pushed.
