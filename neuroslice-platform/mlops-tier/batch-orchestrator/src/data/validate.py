"""Data validation script for the processed 6G dataset.

Checks:
  - No missing values
  - Presence of required columns
  - Normalised columns (cpu_utilization, bandwidth_mbps) within [0, 1]
  - Minimum row count (> 100)

Prints a validation report and raises ValueError on failure.
"""

import sys
from pathlib import Path
import pandas as pd

PROCESSED_PATH = "data/processed/6g_processed.csv"
REQUIRED_COLUMNS = ["cpu_utilization", "bandwidth_mbps", "congestion_flag"]
NORMALISED_COLUMNS = ["cpu_utilization", "bandwidth_mbps"]
MIN_ROW_COUNT = 100
BASE_DIR = Path(__file__).resolve().parents[2]


def _resolve_path(path: str) -> Path:
    """Resolve a data path relative to the batch-orchestrator root."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return BASE_DIR / candidate


def validate(path: str = PROCESSED_PATH) -> None:
    """Validate the processed 6G dataset.

    Args:
        path: Path to the processed CSV file.

    Raises:
        ValueError: When any validation check fails.
    """
    errors = []
    print("=" * 60)
    print("DATA VALIDATION REPORT")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    csv_path = _resolve_path(path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Processed dataset not found at '{csv_path}'. "
            "Run 'make data' (or 'python src/data/preprocess_6g.py') first."
        )

    df = pd.read_csv(csv_path)
    print(f"\n[OK]  Loaded '{csv_path}' - shape: {df.shape}")

    # ------------------------------------------------------------------
    # 1. Required columns
    # ------------------------------------------------------------------
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        msg = f"Missing required columns: {missing_cols}"
        errors.append(msg)
        print(f"[FAIL] {msg}")
    else:
        print(f"[OK]  All required columns present: {REQUIRED_COLUMNS}")

    # ------------------------------------------------------------------
    # 2. No missing values
    # ------------------------------------------------------------------
    null_counts = df[REQUIRED_COLUMNS].isnull().sum()
    if null_counts.any():
        msg = f"Missing values detected:\n{null_counts[null_counts > 0]}"
        errors.append(msg)
        print(f"[FAIL] {msg}")
    else:
        print("[OK]  No missing values in required columns.")

    # ------------------------------------------------------------------
    # 3. Normalised columns within [0, 1]
    # ------------------------------------------------------------------
    for col in NORMALISED_COLUMNS:
        if col in df.columns:
            col_min = df[col].min()
            col_max = df[col].max()
            if col_min < 0 or col_max > 1:
                msg = f"Column '{col}' out of [0,1] range " f"(min={col_min:.4f}, max={col_max:.4f})."
                errors.append(msg)
                print(f"[FAIL] {msg}")
            else:
                print(f"[OK]  '{col}' within [0,1] " f"(min={col_min:.4f}, max={col_max:.4f}).")

    # ------------------------------------------------------------------
    # 4. Minimum row count
    # ------------------------------------------------------------------
    if len(df) <= MIN_ROW_COUNT:
        msg = f"Row count {len(df)} does not exceed minimum {MIN_ROW_COUNT}."
        errors.append(msg)
        print(f"[FAIL] {msg}")
    else:
        print(f"[OK]  Row count {len(df)} exceeds minimum {MIN_ROW_COUNT}.")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    if errors:
        print(f"VALIDATION FAILED – {len(errors)} error(s) found.")
        for e in errors:
            print(f"  • {e}")
        print("=" * 60)
        raise ValueError(f"Data validation failed with {len(errors)} error(s).")
    else:
        print("VALIDATION PASSED – all checks OK.")
        print("=" * 60)


if __name__ == "__main__":
    try:
        validate()
    except (ValueError, FileNotFoundError) as exc:
        print(exc)
        sys.exit(1)
