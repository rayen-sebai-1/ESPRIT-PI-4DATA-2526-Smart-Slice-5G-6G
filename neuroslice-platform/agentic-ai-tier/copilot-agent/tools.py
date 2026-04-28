from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import Any, Dict, Optional

from langchain_core.tools import tool

try:
    from shared.data_access import (
        fetch_influx_kpis_raw as _fetch_influx_kpis_raw,
        fetch_redis_state_raw as _fetch_redis_state_raw,
        normalize_filters,
    )
except ModuleNotFoundError:  # local execution from copilot-agent/
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shared.data_access import (
        fetch_influx_kpis_raw as _fetch_influx_kpis_raw,
        fetch_redis_state_raw as _fetch_redis_state_raw,
        normalize_filters,
    )


logger = logging.getLogger(__name__)


def _extract_slice_id(
    slice_id: Optional[str] = None,
    query_parameters: Optional[Dict[str, Any]] = None,
) -> str:
    filters, _ = normalize_filters(slice_id=slice_id or "", query_parameters=query_parameters)
    return str(filters.get("slice_id") or "slice-001")


@tool
def fetch_influx_kpis(
    query_parameters: Optional[Dict[str, Any]] = None,
    slice_id: Optional[str] = None,
    time_range: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Fetch compact, aggregated telemetry and fault evidence from real InfluxDB.
    Accepts query_parameters with slice_id/domain/entity_id/entity_type/slice_type/time_range, or direct slice_id.
    Pass null/omit any argument that is unknown.
    """
    try:
        normalized_slice_id = _extract_slice_id(slice_id=slice_id, query_parameters=query_parameters)
        return _fetch_influx_kpis_raw(
            slice_id=normalized_slice_id,
            time_range=time_range,
            query_parameters=query_parameters,
        )
    except Exception as exc:  # pragma: no cover - final defensive guard
        logger.exception("fetch_influx_kpis failed: %s", exc)
        return {
            "status": "error",
            "source": "influxdb",
            "error": {"message": str(exc)},
            "telemetry": {},
            "faults": {},
        }


@tool
def fetch_redis_state(
    slice_id: Optional[str] = None,
    query_parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fetch compact live Redis state for a slice, including entity hashes, active faults, and AIOps outputs.
    Pass null/omit slice_id if unknown; the tool will fall back to a default slice.
    """
    try:
        normalized_slice_id = _extract_slice_id(slice_id=slice_id, query_parameters=query_parameters)
        return _fetch_redis_state_raw(slice_id=normalized_slice_id, query_parameters=query_parameters)
    except Exception as exc:  # pragma: no cover - final defensive guard
        logger.exception("fetch_redis_state failed: %s", exc)
        return {
            "status": "error",
            "source": "redis",
            "slice_id": slice_id,
            "error": {"message": str(exc)},
            "active_faults": [],
            "entities": {},
            "aiops": {},
            "cross_domain": {},
            "recent_events": {},
        }

