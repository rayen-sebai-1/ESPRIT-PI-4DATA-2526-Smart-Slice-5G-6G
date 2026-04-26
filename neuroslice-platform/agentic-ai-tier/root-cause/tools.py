from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import Any, Dict

from langchain_core.tools import tool

try:
    from shared.data_access import (
        fetch_influx_kpis_raw as _fetch_influx_kpis_raw,
        fetch_redis_state_raw as _fetch_redis_state_raw,
    )
except ModuleNotFoundError:  # local execution from root-cause/
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shared.data_access import (
        fetch_influx_kpis_raw as _fetch_influx_kpis_raw,
        fetch_redis_state_raw as _fetch_redis_state_raw,
    )


logger = logging.getLogger(__name__)


def fetch_influx_kpis_raw(slice_id: str, time_range: Any = None) -> Dict[str, Any]:
    return _fetch_influx_kpis_raw(slice_id=slice_id, time_range=time_range)


def fetch_redis_state_raw(slice_id: str) -> Dict[str, Any]:
    return _fetch_redis_state_raw(slice_id=slice_id)


@tool
def fetch_influx_kpis(slice_id: str, time_range: str) -> Dict[str, Any]:
    """
    Fetch compact, aggregated telemetry/fault evidence for a slice from real InfluxDB.
    The response is summarized before it is returned to the LLM.
    """
    try:
        return fetch_influx_kpis_raw(slice_id=slice_id, time_range=time_range)
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
def fetch_redis_state(slice_id: str) -> Dict[str, Any]:
    """
    Fetch compact live Redis state for a slice, including entity hashes, active faults, and AIOps outputs.
    """
    try:
        return fetch_redis_state_raw(slice_id=slice_id)
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

