"""Publishing helpers for congestion-detector outputs."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

from aiokafka import AIOKafkaProducer
from influxdb_client import InfluxDBClient, Point, WriteOptions

from config import CongestionConfig
from schemas import CongestionOutputEvent

logger = logging.getLogger(__name__)


class CongestionPublisher:
    def __init__(self, cfg: CongestionConfig, redis_client) -> None:
        self.cfg = cfg
        self.redis = redis_client

        self._kafka_producer: AIOKafkaProducer | None = None
        self._influx_client: InfluxDBClient | None = None
        self._influx_write_api = None

    async def start(self) -> None:
        if self.cfg.kafka_enabled:
            producer = AIOKafkaProducer(bootstrap_servers=self.cfg.kafka_broker)
            for attempt in range(10):
                try:
                    await producer.start()
                    self._kafka_producer = producer
                    logger.info("Kafka output enabled on topic=%s", self.cfg.kafka_topic)
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Kafka producer startup retry (%d/10): %s", attempt + 1, exc)
                    await asyncio.sleep(3)

        if self.cfg.influx_enabled:
            try:
                self._influx_client = InfluxDBClient(
                    url=self.cfg.influx_url,
                    token=self.cfg.influx_token,
                    org=self.cfg.influx_org,
                )
                self._influx_write_api = self._influx_client.write_api(
                    write_options=WriteOptions(batch_size=50, flush_interval=1000, retry_interval=2000)
                )
                logger.info("InfluxDB output enabled measurement=%s", self.cfg.influx_measurement)
            except Exception as exc:  # noqa: BLE001
                logger.warning("InfluxDB output disabled due to startup error: %s", exc)
                self._influx_client = None
                self._influx_write_api = None

    async def stop(self) -> None:
        if self._kafka_producer is not None:
            await self._kafka_producer.stop()
        if self._influx_write_api is not None:
            self._influx_write_api.close()
        if self._influx_client is not None:
            self._influx_client.close()

    async def publish(self, output_event: CongestionOutputEvent) -> None:
        payload = output_event.model_dump(by_alias=True)
        event_json = json.dumps(payload)

        # Redis Stream output contract.
        self.redis.xadd(
            self.cfg.output_stream,
            {"event": event_json},
            maxlen=self.cfg.stream_maxlen,
            approximate=True,
        )

        # Redis latest state for fast API reads.
        entity_id = payload.get("entityId") or "unknown"
        state_key = f"{self.cfg.state_prefix}:{entity_id}"
        state_payload = {
            "eventId": payload.get("eventId"),
            "timestamp": payload.get("timestamp"),
            "service": payload.get("service"),
            "siteId": payload.get("siteId"),
            "sliceId": payload.get("sliceId"),
            "entityId": entity_id,
            "entityType": payload.get("entityType"),
            "severity": payload.get("severity"),
            "score": payload.get("score"),
            "prediction": payload.get("prediction"),
            "modelVersion": payload.get("modelVersion"),
            "sourceEventId": payload.get("sourceEventId"),
            "details": payload.get("details", {}),
        }
        self.redis.hset(state_key, mapping=self._encode_hash(state_payload))
        self.redis.expire(state_key, self.cfg.state_ttl_sec)

        # Enrich existing entity hash so /kpis/latest can include current inference.
        entity_key = f"entity:{entity_id}"
        self.redis.hset(
            entity_key,
            mapping=self._encode_hash(
                {
                    "aiopsCongestionScore": payload.get("score"),
                    "aiopsCongestionPrediction": payload.get("prediction"),
                    "aiopsCongestionSeverity": payload.get("severity"),
                    "aiopsCongestionModelVersion": payload.get("modelVersion"),
                    "aiopsCongestionUpdatedAt": payload.get("timestamp"),
                }
            ),
        )
        self.redis.expire(entity_key, max(self.cfg.state_ttl_sec, 3600))

        if self._kafka_producer is not None:
            try:
                await self._kafka_producer.send_and_wait(self.cfg.kafka_topic, event_json.encode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Kafka publish failed: %s", exc)

        if self._influx_write_api is not None:
            try:
                point = (
                    Point(self.cfg.influx_measurement)
                    .tag("service", self.cfg.service_name)
                    .tag("entity_id", entity_id)
                    .tag("entity_type", payload.get("entityType") or "unknown")
                    .tag("site_id", payload.get("siteId") or "unknown")
                    .tag("slice_id", payload.get("sliceId") or "none")
                    .field("score", float(payload.get("score") or 0.0))
                    .field("severity", float(payload.get("severity") or 0))
                    .field("prediction", str(payload.get("prediction") or "unknown"))
                    .time(payload.get("timestamp"))
                )
                self._influx_write_api.write(bucket=self.cfg.influx_bucket, record=point)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Influx write failed: %s", exc)

    @staticmethod
    def _encode_hash(data: Dict[str, Any]) -> Dict[str, str]:
        encoded: Dict[str, str] = {}
        for key, value in data.items():
            if isinstance(value, str):
                encoded[key] = value
            else:
                encoded[key] = json.dumps(value)
        return encoded
