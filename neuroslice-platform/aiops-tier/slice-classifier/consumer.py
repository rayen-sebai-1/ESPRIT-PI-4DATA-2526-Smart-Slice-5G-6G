"""Stream consumer loop for slice-classifier."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from config import SliceClassifierConfig
from inference import SliceInferencer
from publisher import SlicePublisher
from shared.redis_client import ack_message, ensure_consumer_group, read_group

logger = logging.getLogger(__name__)


class SliceConsumer:
    def __init__(
        self,
        cfg: SliceClassifierConfig,
        redis_client,
        inferencer: SliceInferencer,
        publisher: SlicePublisher,
    ) -> None:
        self.cfg = cfg
        self.redis = redis_client
        self.inferencer = inferencer
        self.publisher = publisher

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

                        output = self.inferencer.infer(event)
                        if output is not None:
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
