"""Redis connection helper for drift-monitor."""
from __future__ import annotations

import redis

from config import get_config

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        cfg = get_config()
        _redis = redis.Redis(
            host=cfg.redis_host,
            port=cfg.redis_port,
            decode_responses=True,
        )
    return _redis
