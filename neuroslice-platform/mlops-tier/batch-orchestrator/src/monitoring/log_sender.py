"""Prediction log sender with Logstash-first delivery and Elasticsearch fallback."""
from __future__ import annotations

import datetime
import json
import os
import urllib.request
from typing import Any, Dict

from elasticsearch import Elasticsearch

DEFAULT_ES_HOST = "http://localhost:9200"
DEFAULT_INDEX_NAME = "smart-slice-predictions"
DEFAULT_LOGSTASH_HTTP_URL = "http://localhost:8081/predictions"


def log_prediction(
    model_name: str,
    input_data: Dict[str, Any],
    prediction: Any,
    confidence: float,
    latency_ms: float,
) -> None:
    """Send a prediction event through Logstash or directly to Elasticsearch."""
    document = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_name": model_name,
        "input_data": input_data,
        "prediction": prediction,
        "confidence": confidence,
        "latency_ms": latency_ms,
    }

    if _monitoring_mode() == "logstash":
        try:
            _send_to_logstash(document)
            return
        except Exception:  # noqa: BLE001
            _send_to_elasticsearch(document)
            return

    _send_to_elasticsearch(document)


def _send_to_logstash(document: Dict[str, Any]) -> None:
    payload = json.dumps(document).encode("utf-8")
    request = urllib.request.Request(
        _logstash_http_url(),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5):  # noqa: S310
        return


def _send_to_elasticsearch(document: Dict[str, Any]) -> None:
    client = Elasticsearch(_es_host())
    client.index(index=_index_name(), body=document)


def _monitoring_mode() -> str:
    return os.getenv("LOG_MONITORING_MODE", "logstash").strip().lower()


def _logstash_http_url() -> str:
    return os.getenv("LOGSTASH_HTTP_URL", DEFAULT_LOGSTASH_HTTP_URL)


def _es_host() -> str:
    return os.getenv("ES_HOST", DEFAULT_ES_HOST)


def _index_name() -> str:
    return os.getenv("ES_INDEX_NAME", DEFAULT_INDEX_NAME)
