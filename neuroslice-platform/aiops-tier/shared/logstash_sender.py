"""Fire-and-forget Logstash HTTP sender for AIOps prediction events.

Called from each service's consumer loop after a successful inference.
Runs the blocking urllib POST in a thread executor so it never stalls
the asyncio event loop. All errors are logged at DEBUG level and swallowed
so a Logstash outage never disrupts the prediction pipeline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_URL = "http://logstash:8081/predictions"


def _enabled() -> bool:
    return os.getenv("LOGSTASH_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def _url() -> str:
    return os.getenv("LOGSTASH_HTTP_URL", _DEFAULT_URL).strip()


def _build_payload(
    service_name: str,
    model: str,
    prediction: str,
    confidence: float,
    site_id: str,
    slice_id: str | None,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "service": {"name": service_name},
        "model": model,
        "prediction": prediction,
        "confidence": round(confidence, 6),
        "event": {"dataset": "smart_slice.predictions", "kind": "event"},
        "site_id": site_id,
        "slice_id": slice_id or "",
        "message": f"{service_name} predicted {prediction} (confidence={confidence:.3f})",
    }


def _post_sync(url: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp.read()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Logstash send skipped (non-fatal): %s", exc)


async def send_prediction(
    service_name: str,
    model: str,
    prediction: str,
    confidence: float,
    site_id: str,
    slice_id: str | None,
    timestamp: str,
) -> None:
    """Async fire-and-forget: POST one prediction event to Logstash."""
    if not _enabled():
        return
    payload = _build_payload(service_name, model, prediction, confidence, site_id, slice_id, timestamp)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _post_sync, _url(), payload)
