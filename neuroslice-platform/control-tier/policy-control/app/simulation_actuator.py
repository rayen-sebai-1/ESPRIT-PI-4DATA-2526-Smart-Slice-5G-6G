"""Scenario B simulation actuator for policy-control.

Applies approved control actions to Redis-only simulation state.
No external PCF/NMS calls are performed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import PolicyControlConfig
from .redis_client import encode_hash


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SimulationActuator:
    def __init__(self, cfg: PolicyControlConfig, redis_client) -> None:
        self.cfg = cfg
        self.redis = redis_client

    def apply(self, action: dict[str, Any]) -> dict[str, Any]:
        action_type = str(action.get("action_type") or "NO_ACTION")
        action_id = str(action.get("action_id") or "")
        alert_id = str(action.get("alert_id") or "")
        entity_id = str(action.get("entity_id") or "unknown")
        slice_id = action.get("slice_id")
        policy_id = str(action.get("policy_id") or "")
        timestamp = _utc_now_iso()

        payload: dict[str, Any] = {
            "action_id": action_id,
            "alert_id": alert_id,
            "entity_id": entity_id,
            "slice_id": slice_id,
            "policy_id": policy_id,
            "action_type": action_type,
            "timestamp": timestamp,
            "simulated": True,
            "keys_written": [],
        }

        if action_type == "RECOMMEND_PCF_QOS_UPDATE":
            qos_key = f"control:actuation:qos:{entity_id}"
            self.redis.set(qos_key, json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
            self.redis.set("control:sim:qos_boost", "0.20")
            payload["keys_written"] = [qos_key, "control:sim:qos_boost"]
            self._publish(payload)

        elif action_type == "RECOMMEND_REROUTE_SLICE":
            reroute_key = f"control:actuation:reroute:{entity_id}"
            self.redis.set(reroute_key, json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
            if slice_id:
                self.redis.set(f"control:sim:reroute_bias:{slice_id}", "0.25")
                payload["keys_written"] = [reroute_key, f"control:sim:reroute_bias:{slice_id}"]
            else:
                self.redis.set("control:sim:reroute_bias", "0.25")
                payload["keys_written"] = [reroute_key, "control:sim:reroute_bias"]
            self._publish(payload)

        elif action_type == "RECOMMEND_SCALE_EDGE_RESOURCE":
            scale_key = f"control:actuation:scale:{entity_id}"
            self.redis.set(scale_key, json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
            self.redis.set(f"control:sim:edge_capacity_boost:{entity_id}", "0.20")
            self.redis.set("control:sim:edge_capacity_boost", "0.20")
            payload["keys_written"] = [
                scale_key,
                f"control:sim:edge_capacity_boost:{entity_id}",
                "control:sim:edge_capacity_boost",
            ]
            self._publish(payload)

        elif action_type == "RECOMMEND_INSPECT_SLICE_POLICY":
            inspect_key = f"control:actuation:inspect:{entity_id}"
            self.redis.set(inspect_key, json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
            payload["keys_written"] = [inspect_key]
            self._publish(payload)

        elif action_type == "INVESTIGATE_CONTEXT":
            investigate_key = f"control:actuation:investigate:{entity_id}"
            self.redis.set(investigate_key, json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
            payload["keys_written"] = [investigate_key]
            self._publish(payload)

        else:
            payload["keys_written"] = []
            payload["note"] = "No actuator mutation for NO_ACTION"

        self.redis.hset(f"control:actuations:{action_id}", mapping=encode_hash(payload))
        self.redis.sadd("control:actuations:index", action_id)
        return payload

    def get_actuation(self, action_id: str) -> dict[str, Any] | None:
        raw = self.redis.hgetall(f"control:actuations:{action_id}")
        if not raw:
            return None
        decoded: dict[str, Any] = {}
        for key, value in raw.items():
            if isinstance(value, str):
                try:
                    decoded[key] = json.loads(value)
                except Exception:
                    decoded[key] = value
            else:
                decoded[key] = value
        return decoded

    def list_actuations(self) -> list[dict[str, Any]]:
        action_ids = list(self.redis.smembers("control:actuations:index"))
        rows: list[dict[str, Any]] = []
        for action_id in action_ids:
            item = self.get_actuation(str(action_id))
            if item is not None:
                rows.append(item)
        rows.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
        return rows

    def _publish(self, payload: dict[str, Any]) -> None:
        self.redis.xadd(
            "stream:control.actuations",
            {
                "event_type": "actuation.executed_simulated",
                "event": json.dumps(payload, separators=(",", ":"), ensure_ascii=True),
                "action_id": str(payload.get("action_id") or ""),
                "action_type": str(payload.get("action_type") or ""),
                "entity_id": str(payload.get("entity_id") or ""),
                "timestamp": str(payload.get("timestamp") or ""),
                "simulated": "true",
            },
            maxlen=self.cfg.stream_maxlen,
            approximate=True,
        )
