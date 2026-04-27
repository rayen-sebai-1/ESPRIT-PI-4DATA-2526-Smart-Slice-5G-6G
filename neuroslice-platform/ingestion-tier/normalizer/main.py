"""
normalizer/main.py
Telemetry Normalizer Service.

Consumes raw events from Redis Streams (VES + NETCONF),
maps them to the canonical CanonicalEvent schema,
publishes to stream:norm.telemetry,
and stores latest entity state in Redis hashes.

Runs as a background asyncio service (no HTTP port needed).
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import os
import redis
from aiokafka import AIOKafkaProducer

sys.path.insert(0, "/shared")

from shared.config import get_config
from shared.models import (
    CanonicalEvent, Domain, DerivedMetrics, EntityType,
    FaultRef, Protocol, RoutingInfo, Severity, SliceType,
)
from shared.redis_client import (
    get_redis, ensure_consumer_group, read_group, ack_message,
    publish_to_stream, set_entity_state,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

cfg = get_config()

CONSUMER_GROUP = "normalizer-group"
CONSUMER_NAME = "normalizer-01"

KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "telemetry-norm")


# ─────────────────────────────────────────────────────────────────────────────
# Field mapping helpers
# ─────────────────────────────────────────────────────────────────────────────

ENTITY_TYPE_MAP: Dict[str, EntityType] = {
    "amf": EntityType.AMF,
    "smf": EntityType.SMF,
    "upf": EntityType.UPF,
    "edge_upf": EntityType.EDGE_UPF,
    "mec_app": EntityType.MEC_APP,
    "compute_node": EntityType.COMPUTE_NODE,
    "gnb": EntityType.GNB,
    "cell": EntityType.CELL,
}

DOMAIN_MAP: Dict[str, Domain] = {
    "core": Domain.CORE,
    "edge": Domain.EDGE,
    "ran": Domain.RAN,
}

SLICE_TYPE_MAP: Dict[str, SliceType] = {
    "eMBB": SliceType.EMBB,
    "URLLC": SliceType.URLLC,
    "mMTC": SliceType.MMTC,
}


def _compute_derived(kpis: dict, internal: dict) -> DerivedMetrics:
    """Compute derived scores from KPIs."""
    # Congestion score
    congestion = 0.0
    if cs := internal.get("congestionScore"):
        congestion = float(cs)
    elif "rbUtilizationPct" in kpis:
        congestion = min(1.0, kpis["rbUtilizationPct"] / 100.0 * 0.7 + kpis.get("packetLossPct", 0) / 10.0 * 0.3)
    elif "queueDepthPct" in kpis:
        congestion = kpis["queueDepthPct"] / 100.0

    health = float(internal.get("healthScore", 1.0 - congestion))
    misrouting = float(internal.get("misroutingScore", 0.0))

    return DerivedMetrics(
        congestionScore=round(congestion, 4),
        healthScore=round(max(0.0, min(1.0, health)), 4),
        misroutingScore=round(misrouting, 4),
    )


def _compute_severity(derived: DerivedMetrics, kpis: dict) -> Severity:
    """Map congestion/health scores to severity level."""
    c = derived.congestion_score
    if c < 0.3:
        return Severity.OK
    elif c < 0.5:
        return Severity.LOW
    elif c < 0.7:
        return Severity.MEDIUM
    elif c < 0.85:
        return Severity.HIGH
    return Severity.CRITICAL


def _build_routing(internal: dict, entity_type: str, slice_type: Optional[str]) -> Optional[RoutingInfo]:
    if "expectedUpf" not in internal:
        return None
    return RoutingInfo(
        expectedUpf=internal.get("expectedUpf", ""),
        actualUpf=internal.get("actualUpf", ""),
        qosProfileExpected=internal.get("qosExpected", slice_type or "").lower(),
        qosProfileActual=internal.get("qosActual", slice_type or "").lower(),
    )


def _normalize_ves(payload: dict) -> Optional[CanonicalEvent]:
    """Map raw VES event to canonical schema."""
    try:
        internal = payload.get("internal", {})
        kpis = payload.get("kpis", {})
        domain_str = payload.get("domain", "")
        entity_type_str = payload.get("entity_type", "").lower()
        slice_type_str = payload.get("slice_type")

        domain = DOMAIN_MAP.get(domain_str, Domain.CORE)
        entity_type = ENTITY_TYPE_MAP.get(entity_type_str, EntityType.AMF)
        slice_type = SLICE_TYPE_MAP.get(slice_type_str) if slice_type_str else None

        derived = _compute_derived(kpis, internal)
        severity = _compute_severity(derived, kpis)
        routing = _build_routing(internal, entity_type_str, slice_type_str)

        return CanonicalEvent(
            eventId=str(uuid.uuid4()),
            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
            domain=domain,
            siteId=payload.get("site_id", cfg.site_id),
            nodeId=payload.get("node_id", "unknown"),
            entityId=payload.get("entity_id", "unknown"),
            entityType=entity_type,
            sliceId=payload.get("slice_id"),
            sliceType=slice_type,
            protocol=Protocol.VES,
            vendor="simulated",
            kpis={k: float(v) for k, v in kpis.items() if isinstance(v, (int, float))},
            derived=derived,
            routing=routing,
            faults=[],
            scenarioId=payload.get("scenario_id", "normal_day"),
            severity=severity,
        )
    except Exception as exc:
        logger.warning("VES normalize error: %s payload=%s", exc, str(payload)[:200])
        return None


def _normalize_netconf(payload: dict) -> Optional[CanonicalEvent]:
    """Map flat NETCONF record to canonical schema."""
    try:
        section = payload.get("section", "")
        domain_str = payload.get("domain", "edge")
        entity_type_str = payload.get("entityType", section).lower()
        managed_el = payload.get("managed_element", "unknown")

        # Extract KPIs — all numeric fields that aren't metadata
        meta_keys = {"source", "managed_element", "timestamp", "schema_version",
                     "scenario_id", "section", "domain", "siteId", "entityType",
                     "delay_ms"}  # delay_ms is a known schema mismatch field
        kpis = {}
        for k, v in payload.items():
            if k not in meta_keys and isinstance(v, (int, float)):
                # Normalize schema mismatch: delay_ms → forwardingLatencyMs
                kpis[k] = float(v)

        # Handle schema mismatch field
        if "delay_ms" in payload and "forwardingLatencyMs" not in kpis:
            kpis["forwardingLatencyMs"] = float(payload["delay_ms"])
            kpis["_schemaMismatch"] = 1.0  # flag for downstream

        domain = DOMAIN_MAP.get(domain_str, Domain.EDGE)
        entity_type = ENTITY_TYPE_MAP.get(entity_type_str, EntityType.EDGE_UPF)
        derived = _compute_derived(kpis, {})
        severity = _compute_severity(derived, kpis)

        return CanonicalEvent(
            eventId=str(uuid.uuid4()),
            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
            domain=domain,
            siteId=payload.get("siteId", cfg.site_id),
            nodeId=managed_el,
            entityId=managed_el,
            entityType=entity_type,
            protocol=Protocol.NETCONF,
            vendor="simulated",
            kpis=kpis,
            derived=derived,
            scenarioId=payload.get("scenario_id", "normal_day"),
            severity=severity,
        )
    except Exception as exc:
        logger.warning("NETCONF normalize error: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Consumer loop
# ─────────────────────────────────────────────────────────────────────────────

async def consume_loop(r: redis.Redis, producer: AIOKafkaProducer) -> None:
    # Setup consumer groups
    ensure_consumer_group(r, cfg.stream_raw_ves, CONSUMER_GROUP)
    ensure_consumer_group(r, cfg.stream_raw_netconf, CONSUMER_GROUP)

    logger.info("Normalizer consumer loop started")
    while True:
        for stream, normalizer_fn, proto in [
            (cfg.stream_raw_ves, _normalize_ves, "ves"),
            (cfg.stream_raw_netconf, _normalize_netconf, "netconf"),
        ]:
            try:
                messages = read_group(r, stream, CONSUMER_GROUP, CONSUMER_NAME, count=50, block_ms=500)
                for msg_id, fields in messages:
                    raw_payload = fields.get("payload")
                    if not raw_payload:
                        ack_message(r, stream, CONSUMER_GROUP, msg_id)
                        continue

                    payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                    event = normalizer_fn(payload)
                    if event:
                        event_dict = event.model_dump(by_alias=True)
                        event_json_str = json.dumps(event_dict)
                        # Publish to Redis
                        publish_to_stream(r, cfg.stream_norm_telemetry, {"event": event_json_str})
                        # Publish to Kafka
                        kafka_payload = json.dumps({"event": event_json_str}).encode("utf-8")
                        await producer.send_and_wait(KAFKA_TOPIC, kafka_payload)
                        
                        # Store latest entity state
                        set_entity_state(r, event.entity_id, {
                            "entityId": event.entity_id,
                            "nodeId": event.node_id,
                            "siteId": event.site_id,
                            "sliceId": event.slice_id,
                            "sliceType": event.slice_type.value if event.slice_type else None,
                            "entityType": event.entity_type.value if event.entity_type else None,
                            "domain": event.domain.value if event.domain else None,
                            "healthScore": event.derived.health_score,
                            "congestionScore": event.derived.congestion_score,
                            "misroutingScore": event.derived.misrouting_score,
                            "kpis": json.dumps(event.kpis),
                            "active_faults": [f.fault_id for f in event.faults],
                            "lastUpdated": event.timestamp,
                            "timestamp": event.timestamp,
                            "scenarioId": event.scenario_id,
                            "severity": event.severity,
                        })

                    ack_message(r, stream, CONSUMER_GROUP, msg_id)
            except Exception as exc:
                logger.warning("Consumer error on %s: %s", stream, exc)

        await asyncio.sleep(0.1)


async def main() -> None:
    r = None
    for attempt in range(20):
        try:
            r = get_redis()
            r.ping()
            logger.info("Normalizer connected to Redis")
            break
        except Exception as exc:
            logger.warning("Waiting for Redis (%d/20): %s", attempt + 1, exc)
            await asyncio.sleep(3)

    logger.info("Connecting to Kafka...")
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
    for attempt in range(10):
        try:
            await producer.start()
            logger.info("Normalizer connected to Kafka")
            break
        except Exception as exc:
            logger.warning("Waiting for Kafka (%d/10): %s", attempt + 1, exc)
            await asyncio.sleep(5)
            
    try:
        await consume_loop(r, producer)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
