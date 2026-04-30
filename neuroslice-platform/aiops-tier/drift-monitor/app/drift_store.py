"""Redis state management for drift-monitor.

Stores:
  - Latest drift state per model:  aiops:drift:{model_name}  (Redis hash)
  - Drift event stream:            events.drift              (Redis stream)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import redis

from schemas import DriftState

logger = logging.getLogger(__name__)

DRIFT_STATE_KEY = "aiops:drift:{model_name}"
DRIFT_EVENTS_STREAM = "events.drift"
STREAM_MAXLEN = 5000


class DriftStore:
    def __init__(self, r: redis.Redis) -> None:
        self._r = r

    def save_state(self, state: DriftState) -> None:
        key = DRIFT_STATE_KEY.format(model_name=state.model_name)
        data = state.model_dump()
        mapping = {
            k: json.dumps(v) if not isinstance(v, str) else v for k, v in data.items()
        }
        try:
            self._r.hset(key, mapping=mapping)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to save drift state for %s: %s", state.model_name, exc)

    def get_state(self, model_name: str) -> Optional[Dict[str, Any]]:
        key = DRIFT_STATE_KEY.format(model_name=model_name)
        raw = self._r.hgetall(key)
        if not raw:
            return None
        result: Dict[str, Any] = {}
        for k, v in raw.items():
            try:
                result[k] = json.loads(v)
            except Exception:  # noqa: BLE001
                result[k] = v
        return result

    def get_all_states(self, model_names: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        return {name: self.get_state(name) for name in model_names}

    def publish_drift_event(self, event_data: Dict[str, Any]) -> None:
        try:
            self._r.xadd(
                DRIFT_EVENTS_STREAM,
                {"event": json.dumps(event_data)},
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to publish drift event to Redis stream: %s", exc)

    def read_recent_events(self, count: int = 50) -> List[Dict[str, Any]]:
        try:
            raw = self._r.xrevrange(DRIFT_EVENTS_STREAM, count=count)
        except Exception:  # noqa: BLE001
            return []
        events: List[Dict[str, Any]] = []
        for _, fields in raw:
            raw_event = fields.get("event")
            if not raw_event:
                continue
            try:
                events.append(
                    json.loads(raw_event) if isinstance(raw_event, str) else raw_event
                )
            except Exception:  # noqa: BLE001
                continue
        return events
