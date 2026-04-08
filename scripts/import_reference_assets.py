from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.neuroslice_common.reference_data import import_reference_assets


def main() -> None:
    data_root = Path("data")
    manifest = import_reference_assets(data_root)
    copied_count = len(manifest.get("copied", []))
    assets_count = len(manifest.get("assets", []))
    print(f"[reference-assets] OK: {copied_count} assets copied, {assets_count} assets indexed.")
    print("[reference-assets] Manifest:", data_root / "reference_assets_manifest.json")


if __name__ == "__main__":
    main()
