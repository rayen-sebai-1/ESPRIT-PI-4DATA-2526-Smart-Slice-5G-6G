"""InfluxDB writer for drift-monitor."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_client: Any = None
_write_api: Any = None


def get_write_api(url: str, token: str, org: str) -> Any:
    global _client, _write_api
    if _write_api is not None:
        return _write_api
    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS

        _client = InfluxDBClient(url=url, token=token, org=org)
        _write_api = _client.write_api(write_options=SYNCHRONOUS)
        logger.info("InfluxDB write API initialized: %s org=%s", url, org)
    except Exception as exc:  # noqa: BLE001
        logger.warning("InfluxDB unavailable (drift scores will not be written): %s", exc)
        _write_api = None
    return _write_api


def write_drift_point(
    write_api: Any,
    bucket: str,
    org: str,
    model_name: str,
    drift_data: Dict[str, Any],
) -> None:
    if write_api is None:
        return
    try:
        from influxdb_client import Point

        p = (
            Point("aiops_drift")
            .tag("model_name", model_name)
            .tag("is_drift", str(drift_data.get("is_drift", False)).lower())
            .tag("severity", str(drift_data.get("severity", "NONE")))
            .field("p_value", float(drift_data.get("p_val") or 1.0))
            .field("window_size", int(drift_data.get("window_size") or 0))
            .field("reference_sample_count", int(drift_data.get("reference_sample_count") or 0))
        )
        if drift_data.get("drift_score") is not None:
            p = p.field("drift_score", float(drift_data["drift_score"]))

        write_api.write(bucket=bucket, org=org, record=p)
    except Exception as exc:  # noqa: BLE001
        logger.debug("InfluxDB write failed for %s: %s", model_name, exc)
