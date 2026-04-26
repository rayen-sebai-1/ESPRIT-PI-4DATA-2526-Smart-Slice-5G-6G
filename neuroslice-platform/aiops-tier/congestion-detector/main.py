"""Entrypoint for the congestion-detector runtime service."""
from __future__ import annotations

import asyncio
import logging

from config import get_config
from consumer import CongestionConsumer
from inference import CongestionInferencer
from model_loader import CongestionModelLoader
from publisher import CongestionPublisher
from shared.model_hot_reload import should_reload_promoted_model
from shared.redis_client import get_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("congestion-detector")


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


async def _hot_reload_models(
    *,
    cfg,
    loader: CongestionModelLoader,
    inferencer: CongestionInferencer,
) -> None:
    interval = max(5, int(cfg.model_poll_interval_sec))
    while True:
        await asyncio.sleep(interval)
        try:
            current = inferencer.bundle
            if not should_reload_promoted_model(
                registry_path=cfg.model_registry_path,
                model_name=cfg.registry_model_name,
                current_version=current.model_version,
                current_model_source=current.model_source,
                current_metadata_mtime_ns=current.metadata_mtime_ns,
                current_model_mtime_ns=current.model_mtime_ns,
            ):
                continue

            next_bundle = loader.load()
            if not next_bundle.loaded:
                continue

            if (
                next_bundle.model_version != current.model_version
                or next_bundle.model_source != current.model_source
                or next_bundle.model_format != current.model_format
                or next_bundle.metadata_mtime_ns != current.metadata_mtime_ns
                or next_bundle.model_mtime_ns != current.model_mtime_ns
            ):
                inferencer.update_bundle(next_bundle)
                logger.info(
                    "Hot-reloaded congestion model to version=%s source=%s",
                    next_bundle.model_version,
                    next_bundle.model_source,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Congestion model hot-reload check failed: %s", exc)


async def main() -> None:
    cfg = get_config()
    logger.info("Starting %s", cfg.service_name)

    redis_client = await _wait_for_redis()

    loader = CongestionModelLoader(cfg)
    model_bundle = loader.load()
    inferencer = CongestionInferencer(cfg, model_bundle)

    publisher = CongestionPublisher(cfg, redis_client)
    await publisher.start()

    consumer = CongestionConsumer(cfg, redis_client, inferencer, publisher)
    reload_task = asyncio.create_task(_hot_reload_models(cfg=cfg, loader=loader, inferencer=inferencer))

    try:
        await consumer.run_forever()
    finally:
        reload_task.cancel()
        await asyncio.gather(reload_task, return_exceptions=True)
        await publisher.stop()


if __name__ == "__main__":
    asyncio.run(main())
