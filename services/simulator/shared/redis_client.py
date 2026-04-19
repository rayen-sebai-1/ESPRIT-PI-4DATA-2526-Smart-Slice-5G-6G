"""
shared/redis_client.py
Helpers for connecting to Redis and working with Streams.
All services import from here to avoid duplication.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import redis

from .config import get_config

logger = logging.getLogger(__name__)


def get_redis() -> redis.Redis:
    """Return a Redis connection using config values."""
    cfg = get_config()
    return redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=cfg.redis_db,
        decode_responses=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stream helpers
# ─────────────────────────────────────────────────────────────────────────────

def publish_to_stream(
    r: redis.Redis,
    stream: str,
    payload: Dict[str, Any],
    maxlen: Optional[int] = None,
) -> str:
    """
    Publish a dict to a Redis Stream.
    All values are JSON-serialised so complex objects survive the round-trip.
    Returns the message ID assigned by Redis.
    """
    cfg = get_config()
    encoded = {k: json.dumps(v) if not isinstance(v, str) else v for k, v in payload.items()}
    msg_id = r.xadd(stream, encoded, maxlen=maxlen or cfg.stream_maxlen, approximate=True)
    return msg_id


def read_stream_latest(
    r: redis.Redis,
    stream: str,
    count: int = 100,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Return the most recent `count` messages from a stream (no consumer group)."""
    try:
        raw = r.xrevrange(stream, count=count)
    except redis.exceptions.ResponseError:
        return []
    result = []
    for msg_id, fields in raw:
        decoded = {k: _try_json(v) for k, v in fields.items()}
        result.append((msg_id, decoded))
    return result


def ensure_consumer_group(r: redis.Redis, stream: str, group: str) -> None:
    """Create a consumer group if it does not already exist."""
    try:
        r.xgroup_create(stream, group, id="$", mkstream=True)
        logger.info("Created consumer group %s on %s", group, stream)
    except redis.exceptions.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def read_group(
    r: redis.Redis,
    stream: str,
    group: str,
    consumer: str,
    count: int = 50,
    block_ms: int = 1000,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Read new messages from a stream via a consumer group."""
    try:
        raw = r.xreadgroup(
            group, consumer, {stream: ">"}, count=count, block=block_ms
        )
    except redis.exceptions.ResponseError:
        return []
    if not raw:
        return []
    result = []
    for _stream, messages in raw:
        for msg_id, fields in messages:
            decoded = {k: _try_json(v) for k, v in fields.items()}
            result.append((msg_id, decoded))
    return result


def ack_message(r: redis.Redis, stream: str, group: str, msg_id: str) -> None:
    r.xack(stream, group, msg_id)


# ─────────────────────────────────────────────────────────────────────────────
# Hash helpers — latest entity state
# ─────────────────────────────────────────────────────────────────────────────

def set_entity_state(r: redis.Redis, entity_id: str, state: Dict[str, Any]) -> None:
    """Store the latest entity state in a Redis hash for fast API reads."""
    key = f"entity:{entity_id}"
    encoded = {k: json.dumps(v) if not isinstance(v, str) else v for k, v in state.items()}
    r.hset(key, mapping=encoded)
    r.expire(key, 3600)  # auto-expire after 1 hour of inactivity


def get_entity_state(r: redis.Redis, entity_id: str) -> Optional[Dict[str, Any]]:
    key = f"entity:{entity_id}"
    raw = r.hgetall(key)
    if not raw:
        return None
    return {k: _try_json(v) for k, v in raw.items()}


def list_entity_ids(r: redis.Redis, pattern: str = "entity:*") -> List[str]:
    keys = r.keys(pattern)
    return [k.replace("entity:", "") for k in keys]


# ─────────────────────────────────────────────────────────────────────────────
# Internal
# ─────────────────────────────────────────────────────────────────────────────

def _try_json(value: str) -> Any:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value
