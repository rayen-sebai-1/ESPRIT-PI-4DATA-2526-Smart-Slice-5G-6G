"""Redis Stream consumer for Control Tier alerts."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis

from .action_store import ActionStore
from .config import PolicyControlConfig
from .redis_client import ack_message, ensure_consumer_group, read_group

logger = logging.getLogger(__name__)


class PolicyConsumer:
    def __init__(self, cfg: PolicyControlConfig, redis_client: redis.Redis, store: ActionStore) -> None:
        self.cfg = cfg
        self.redis = redis_client
        self.store = store
        self._running = True

    def stop(self) -> None:
        self._running = False

    async def run_forever(self) -> None:
        ensure_consumer_group(self.redis, self.cfg.input_stream, self.cfg.consumer_group)
        logger.info(
            "Consuming alert stream=%s group=%s consumer=%s",
            self.cfg.input_stream,
            self.cfg.consumer_group,
            self.cfg.consumer_name,
        )

        while self._running:
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
                        alert = self._extract_alert(fields)
                        if str(alert.get("status") or "").upper() != "RESOLVED":
                            self.store.upsert_from_alert(alert)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to process alert message %s: %s", msg_id, exc)
                    finally:
                        ack_message(self.redis, self.cfg.input_stream, self.cfg.consumer_group, msg_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("Policy consumer loop error: %s", exc)
                await asyncio.sleep(1.0)

    @staticmethod
    def _extract_alert(fields: dict[str, Any]) -> dict[str, Any]:
        raw = fields.get("alert") or fields.get("event") or fields.get("payload")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return dict(fields)
