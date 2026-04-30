"""Stream consumer loop for sla-assurance."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from config import SlaAssuranceConfig
from inference import SlaInferencer
from publisher import SlaPublisher
from shared.metrics import (
    aiops_events_processed,
    aiops_fallback_mode,
    aiops_inference_latency,
    aiops_last_event_timestamp,
    aiops_model_loaded,
    aiops_predictions,
    aiops_service_enabled,
)
from shared.runtime_control import RuntimeControlGate
from shared.redis_client import ack_message, ensure_consumer_group, read_group

logger = logging.getLogger(__name__)


class SlaConsumer:
    def __init__(
        self,
        cfg: SlaAssuranceConfig,
        redis_client,
        inferencer: SlaInferencer,
        publisher: SlaPublisher,
    ) -> None:
        self.cfg = cfg
        self.redis = redis_client
        self.inferencer = inferencer
        self.publisher = publisher
        self._model_name = cfg.registry_model_name
        self._runtime_gate = RuntimeControlGate(redis_client, cfg.service_name)

    async def run_forever(self) -> None:
        ensure_consumer_group(self.redis, self.cfg.input_stream, self.cfg.consumer_group)
        logger.info(
            "Consuming stream=%s group=%s consumer=%s",
            self.cfg.input_stream,
            self.cfg.consumer_group,
            self.cfg.consumer_name,
        )

        while True:
            try:
                if not self._runtime_gate.is_enabled():
                    aiops_service_enabled.labels(service=self.cfg.service_name).set(0)
                    await asyncio.sleep(0.25)
                    continue
                aiops_service_enabled.labels(service=self.cfg.service_name).set(1)
                messages = read_group(
                    self.redis,
                    self.cfg.input_stream,
                    self.cfg.consumer_group,
                    self.cfg.consumer_name,
                    count=self.cfg.read_count,
                    block_ms=self.cfg.block_ms,
                )

                if not messages:
                    await asyncio.sleep(0.05)
                    continue

                for msg_id, fields in messages:
                    try:
                        event = self._extract_event(fields)
                        if event is None:
                            continue

                        started = time.perf_counter()
                        output = self.inferencer.infer(event)
                        latency = time.perf_counter() - started
                        bundle = self.inferencer.bundle
                        now = time.time()

                        aiops_events_processed.labels(
                            service=self.cfg.service_name,
                            model_name=self._model_name,
                        ).inc()
                        aiops_inference_latency.labels(
                            service=self.cfg.service_name,
                            model_name=self._model_name,
                        ).observe(latency)
                        aiops_last_event_timestamp.labels(
                            service=self.cfg.service_name,
                            model_name=self._model_name,
                        ).set(now)
                        aiops_model_loaded.labels(
                            service=self.cfg.service_name,
                            model_name=self._model_name,
                        ).set(1 if bundle.loaded else 0)
                        aiops_fallback_mode.labels(
                            service=self.cfg.service_name,
                            model_name=self._model_name,
                        ).set(1 if bundle.fallback_mode else 0)
                        if output is not None:
                            aiops_predictions.labels(
                                service=self.cfg.service_name,
                                model_name=self._model_name,
                                prediction=output.prediction,
                            ).inc()
                            await self.publisher.publish(output)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed processing message %s: %s", msg_id, exc)
                    finally:
                        ack_message(self.redis, self.cfg.input_stream, self.cfg.consumer_group, msg_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Consumer loop error: %s", exc)
                await asyncio.sleep(1.0)

    @staticmethod
    def _extract_event(fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raw = fields.get("event") or fields.get("payload")
        if raw is None:
            return None

        if isinstance(raw, dict):
            return raw

        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                logger.debug("Dropping malformed JSON payload")
                return None

        return None
