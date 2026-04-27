"""
kafka-influx-consumer/main.py
Consumes normalized telemetry from Kafka and writes it to InfluxDB.
Also polls Redis faults:active and writes a dedicated 'faults' measurement
so Grafana can display real-time active fault counts and severities.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

import redis as redis_lib
from aiokafka import AIOKafkaConsumer
from influxdb_client import InfluxDBClient, Point, WriteOptions

sys.path.insert(0, "/shared")

logger = logging.getLogger("kafka-influx-consumer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "localhost:29092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "telemetry-norm")

INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN", "neuroslice_token_12345")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "neuroslice")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "telemetry")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
SITE_ID = os.environ.get("SITE_ID", "TT-SFAX-02")


# ─────────────────────────────────────────────────────────────────────────────
# Fault poller — reads faults:active from Redis, writes to InfluxDB
# ─────────────────────────────────────────────────────────────────────────────

async def fault_poller(write_api) -> None:
    """
    Background loop: polls faults:active from Redis every 5s and writes
    a 'faults' measurement to InfluxDB so Grafana can chart them.
    """
    r = None
    for attempt in range(20):
        try:
            r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            r.ping()
            logger.info("Fault poller connected to Redis")
            break
        except Exception as exc:
            logger.warning("Fault poller waiting for Redis (%d/20): %s", attempt + 1, exc)
            await asyncio.sleep(3)

    logger.info("Fault poller started — polling every 5s")
    while True:
        try:
            raw = r.hgetall("faults:active")
            now = datetime.now(timezone.utc).isoformat()
            active_count = len(raw)

            # Aggregate count point — used by "Active Faults" stat panel
            agg_point = (
                Point("faults")
                .tag("type", "aggregate")
                .tag("site_id", SITE_ID)
                .field("active_count", float(active_count))
                .time(now)
            )
            write_api.write(bucket=INFLUXDB_BUCKET, record=agg_point)

            # One point per active fault — used by per-fault detail panels
            for fault_id, fault_json in raw.items():
                try:
                    fault = json.loads(fault_json)
                    entities = fault.get("affected_entities", [])
                    fault_site = fault.get("site_id", SITE_ID)
                    fp = (
                        Point("faults")
                        .tag("type", "fault")
                        .tag("fault_id", fault_id)
                        .tag("fault_type", fault.get("fault_type", "unknown"))
                        .tag("scenario_id", fault.get("scenario_id", "manual"))
                        .tag("affected_entities", ",".join(entities))
                        .tag("site_id", fault_site)
                        .field("severity", float(fault.get("severity", 1)))
                        .field("active", 1.0)
                        .time(now)
                    )
                    write_api.write(bucket=INFLUXDB_BUCKET, record=fp)
                except Exception as fe:
                    logger.warning("Could not parse fault %s: %s", fault_id, fe)

        except Exception as exc:
            logger.warning("Fault poller error: %s", exc)

        await asyncio.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# Kafka → InfluxDB consumer
# ─────────────────────────────────────────────────────────────────────────────

async def consume_loop(write_api) -> None:
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id="influxdb-writer-group",
        auto_offset_reset="latest"
    )

    logger.info("Connecting to Kafka at %s...", KAFKA_BROKER)
    for attempt in range(10):
        try:
            await consumer.start()
            logger.info("Connected to Kafka")
            break
        except Exception as e:
            logger.warning("Waiting for Kafka (%d/10): %s", attempt + 1, e)
            await asyncio.sleep(5)
    else:
        logger.error("Failed to connect to Kafka")
        sys.exit(1)

    try:
        logger.info("Listening for messages on topic: %s", KAFKA_TOPIC)
        async for msg in consumer:
            try:
                payload_str = msg.value.decode("utf-8")
                wrapper = json.loads(payload_str)
                event_str = wrapper.get("event")
                if not event_str:
                    continue

                event = json.loads(event_str)
                timestamp = event.get("timestamp")
                domain = event.get("domain", "")
                entity_id = event.get("entityId", "")
                entity_type = event.get("entityType", "")
                slice_id = event.get("sliceId") or "none"
                slice_type = event.get("sliceType") or "none"
                site_id = event.get("siteId") or "unknown"

                point = (
                    Point("telemetry")
                    .tag("domain", domain)
                    .tag("entity_id", entity_id)
                    .tag("entity_type", entity_type)
                    .tag("slice_id", slice_id)
                    .tag("slice_type", slice_type)
                    .tag("site_id", site_id)
                )

                # KPI fields
                for k, v in event.get("kpis", {}).items():
                    if isinstance(v, (int, float)):
                        point.field(f"kpi_{k}", float(v))

                # Derived metric fields
                for k, v in event.get("derived", {}).items():
                    if isinstance(v, (int, float)):
                        point.field(f"derived_{k}", float(v))

                # Map severity string → numeric level so it can be charted/aggregated
                severity = event.get("severity")
                if severity:
                    sev_levels = {"ok": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
                    point.field("severity", float(sev_levels.get(str(severity).lower(), 0)))
                    point.tag("severity_label", str(severity))

                if timestamp:
                    point.time(timestamp)

                write_api.write(bucket=INFLUXDB_BUCKET, record=point)

            except Exception as e:
                logger.error("Error processing message: %s", e)
    finally:
        await consumer.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint — run both loops concurrently
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("Connecting to InfluxDB at %s...", INFLUXDB_URL)
    influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = influx_client.write_api(
        write_options=WriteOptions(batch_size=100, flush_interval=1000, retry_interval=2000)
    )

    try:
        await asyncio.gather(
            consume_loop(write_api),
            fault_poller(write_api),
        )
    finally:
        write_api.close()
        influx_client.close()


if __name__ == "__main__":
    asyncio.run(main())
