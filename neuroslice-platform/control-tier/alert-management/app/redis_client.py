"""Redis helpers for Alert Management."""
from __future__ import annotations

import json
import logging
from typing import Any

import redis

from .config import AlertManagementConfig, get_config

logger = logging.getLogger(__name__)


def get_redis(cfg: AlertManagementConfig | None = None) -> redis.Redis:
    resolved = cfg or get_config()
    return redis.Redis(
        host=resolved.redis_host,
        port=resolved.redis_port,
        db=resolved.redis_db,
        decode_responses=True,
    )


def encode_hash(data: dict[str, Any]) -> dict[str, str]:
    encoded: dict[str, str] = {}
    for key, value in data.items():
        if value is None:
            encoded[key] = ""
        elif isinstance(value, str):
            encoded[key] = value
        else:
            encoded[key] = json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    return encoded


def decode_hash(raw: dict[str, Any]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in raw.items():
        if value == "":
            decoded[key] = None
        elif isinstance(value, str):
            decoded[key] = try_json(value)
        else:
            decoded[key] = value
    return decoded


def try_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def ensure_consumer_group(r: redis.Redis, stream: str, group: str) -> None:
    try:
        r.xgroup_create(stream, group, id="$", mkstream=True)
        logger.info("Created consumer group %s on %s", group, stream)
    except redis.exceptions.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def read_group(
    r: redis.Redis,
    streams: list[str],
    group: str,
    consumer: str,
    *,
    count: int,
    block_ms: int,
) -> list[tuple[str, str, dict[str, Any]]]:
    try:
        raw = r.xreadgroup(
            group,
            consumer,
            {stream: ">" for stream in streams},
            count=count,
            block=block_ms,
        )
    except redis.exceptions.ResponseError as exc:
        logger.warning("Redis stream read failed: %s", exc)
        return []

    messages: list[tuple[str, str, dict[str, Any]]] = []
    for stream, stream_messages in raw or []:
        for msg_id, fields in stream_messages:
            messages.append((stream, msg_id, {key: try_json(value) for key, value in fields.items()}))
    return messages


def ack_message(r: redis.Redis, stream: str, group: str, msg_id: str) -> None:
    r.xack(stream, group, msg_id)


def publish_event(
    r: redis.Redis,
    stream: str,
    *,
    event_type: str,
    field_name: str,
    payload: dict[str, Any],
    maxlen: int,
) -> str:
    return r.xadd(
        stream,
        {
            "event_type": event_type,
            field_name: json.dumps(payload, separators=(",", ":"), ensure_ascii=True),
        },
        maxlen=maxlen,
        approximate=True,
    )
