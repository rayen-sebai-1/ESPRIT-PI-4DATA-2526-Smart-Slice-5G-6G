"""Entrypoint for the sla-assurance runtime service."""
from __future__ import annotations

import asyncio
import logging

from config import get_config
from consumer import SlaConsumer
from inference import SlaInferencer
from model_loader import SlaModelLoader
from publisher import SlaPublisher
from shared.redis_client import get_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("sla-assurance")


async def _wait_for_redis(max_attempts: int = 30, sleep_sec: float = 2.0):
    for attempt in range(max_attempts):
        try:
            redis_client = get_redis()
            redis_client.ping()
            logger.info("Connected to Redis")
            return redis_client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Waiting for Redis (%d/%d): %s", attempt + 1, max_attempts, exc)
            await asyncio.sleep(sleep_sec)
    raise RuntimeError("Could not connect to Redis")


async def main() -> None:
    cfg = get_config()
    logger.info("Starting %s", cfg.service_name)

    redis_client = await _wait_for_redis()

    model_bundle = SlaModelLoader(cfg).load()
    inferencer = SlaInferencer(cfg, model_bundle)

    publisher = SlaPublisher(cfg, redis_client)
    await publisher.start()

    consumer = SlaConsumer(cfg, redis_client, inferencer, publisher)

    try:
        await consumer.run_forever()
    finally:
        await publisher.stop()


if __name__ == "__main__":
    asyncio.run(main())
