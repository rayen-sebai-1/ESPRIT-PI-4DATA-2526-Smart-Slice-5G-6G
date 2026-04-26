"""Example sender for AIOps prediction events to Logstash HTTP input."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.error
import urllib.request
from typing import Any

DEFAULT_ENDPOINT = "http://logstash:8081/predictions"


def build_prediction_event(
    service_name: str,
    model: str,
    prediction: str,
    confidence: float,
    site_id: str,
    slice_id: str,
    kpis: dict[str, Any],
) -> dict[str, Any]:
    """Return a schema-aligned prediction payload for Logstash ingestion."""
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    return {
        "timestamp": now,
        "service": {"name": service_name},
        "model": model,
        "prediction": prediction,
        "confidence": confidence,
        "event": {
            "dataset": "smart_slice.predictions",
            "kind": "event",
        },
        "site_id": site_id,
        "slice_id": slice_id,
        "kpis": kpis,
        "message": f"{service_name} predicted {prediction} (confidence={confidence:.3f})",
    }


def send_prediction_event(endpoint: str, event: dict[str, Any]) -> None:
    payload = json.dumps(event).encode("utf-8")
    request = urllib.request.Request(
        url=endpoint,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"Logstash response: HTTP {response.status} - {body}")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Logstash rejected event ({exc.code}): {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Logstash endpoint {endpoint}: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a sample AIOps prediction event to Logstash.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Logstash HTTP input endpoint.")
    parser.add_argument("--service", default="congestion-detector", help="AIOps service name.")
    parser.add_argument("--model", default="congestion_5g", help="Model identifier.")
    parser.add_argument("--prediction", default="anomaly", help="Prediction label.")
    parser.add_argument("--confidence", type=float, default=0.92, help="Prediction confidence in [0, 1].")
    parser.add_argument("--site-id", default="TT-SFAX-02", help="Site identifier.")
    parser.add_argument("--slice-id", default="slice-embb-001", help="Slice identifier.")
    args = parser.parse_args()

    event = build_prediction_event(
        service_name=args.service,
        model=args.model,
        prediction=args.prediction,
        confidence=args.confidence,
        site_id=args.site_id,
        slice_id=args.slice_id,
        kpis={
            "latency_ms": 12.8,
            "throughput_mbps": 780.2,
            "packet_loss_pct": 0.21,
            "prb_utilization_pct": 87.5,
        },
    )

    send_prediction_event(args.endpoint, event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
