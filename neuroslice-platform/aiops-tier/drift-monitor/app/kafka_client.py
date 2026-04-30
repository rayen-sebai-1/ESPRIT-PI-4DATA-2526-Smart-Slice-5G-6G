"""Kafka producer for drift-monitor."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_producer: Any = None


def get_producer(bootstrap_servers: str) -> Any:
    global _producer
    if _producer is not None:
        return _producer
    try:
        from kafka import KafkaProducer

        _producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
            request_timeout_ms=5000,
        )
        logger.info("Kafka producer connected: %s", bootstrap_servers)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Kafka producer unavailable (drift alerts will not reach Kafka): %s", exc)
        _producer = None
    return _producer


def publish(producer: Any, topic: str, message: Dict[str, Any]) -> None:
    if producer is None:
        return
    try:
        producer.send(topic, message)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to publish to Kafka topic %s: %s", topic, exc)
