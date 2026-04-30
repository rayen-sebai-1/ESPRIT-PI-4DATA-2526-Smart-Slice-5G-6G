"""Redis-backed action persistence and lifecycle operations."""
from __future__ import annotations

from typing import Any

import redis

from .config import PolicyControlConfig
from .policy_engine import PolicyEngine
from .redis_client import decode_hash, encode_hash, publish_event
from .schemas import Action, ActionStatus, utc_now_iso


TERMINAL_STATUSES = {
    ActionStatus.REJECTED.value,
    ActionStatus.EXECUTED_SIMULATED.value,
    ActionStatus.FAILED.value,
}


class ActionStore:
    def __init__(self, cfg: PolicyControlConfig, redis_client: redis.Redis, policy_engine: PolicyEngine) -> None:
        self.cfg = cfg
        self.redis = redis_client
        self.policy_engine = policy_engine

    def list_actions(self) -> list[dict[str, Any]]:
        action_ids = list(self.redis.smembers("control:actions:index"))
        actions = [action for action_id in action_ids if (action := self.get_action(action_id)) is not None]
        actions.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        return actions

    def get_action(self, action_id: str) -> dict[str, Any] | None:
        raw = self.redis.hgetall(self._action_key(action_id))
        if not raw:
            return None
        return decode_hash(raw)

    def upsert_from_alert(self, alert: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
        if str(alert.get("status") or "").upper() == "RESOLVED":
            return None

        alert_id = str(alert.get("alert_id") or "")
        if not alert_id:
            return None

        existing_id = self.redis.get(self._by_alert_key(alert_id))
        existing = self.get_action(existing_id) if existing_id else None
        if existing is not None:
            if str(existing.get("status")) == ActionStatus.PENDING_APPROVAL.value:
                updated = self._apply_latest_decision(existing, alert)
                self._save(updated)
                self._publish("action.updated", updated)
                return updated, "action.updated"
            return existing, "action.unchanged"

        decision = self.policy_engine.decide(alert)
        action = Action(
            alert_id=alert_id,
            entity_id=str(alert.get("entity_id") or "unknown"),
            slice_id=self._optional_str(alert.get("slice_id")),
            domain=self._optional_str(alert.get("domain")),
            action_type=decision.action_type,
            risk_level=decision.risk_level,
            requires_approval=decision.requires_approval,
            status=decision.status,
            reason=decision.reason,
            policy_id=decision.policy_id,
        ).model_dump(mode="json")
        self._save(action)
        self.redis.set(self._by_alert_key(alert_id), action["action_id"])
        self._publish("action.created", action)
        return action, "action.created"

    def approve(self, action_id: str) -> dict[str, Any] | None:
        action = self.get_action(action_id)
        if action is None:
            return None
        if action.get("status") != ActionStatus.PENDING_APPROVAL.value:
            raise ValueError("Only PENDING_APPROVAL actions can be approved.")
        action["status"] = ActionStatus.APPROVED.value
        action["updated_at"] = utc_now_iso()
        self._save(action)
        self._publish("action.approved", action)
        return action

    def reject(self, action_id: str) -> dict[str, Any] | None:
        action = self.get_action(action_id)
        if action is None:
            return None
        if action.get("status") in TERMINAL_STATUSES:
            raise ValueError("Terminal actions cannot be rejected again.")
        action["status"] = ActionStatus.REJECTED.value
        action["updated_at"] = utc_now_iso()
        self._save(action)
        self._publish("action.rejected", action)
        return action

    def execute(self, action_id: str) -> dict[str, Any] | None:
        action = self.get_action(action_id)
        if action is None:
            return None
        if action.get("status") != ActionStatus.APPROVED.value:
            raise ValueError("Only APPROVED actions can be executed.")
        action["status"] = ActionStatus.EXECUTED_SIMULATED.value
        action["execution_note"] = "Simulated execution — no real PCF/RAN integration in Scenario B."
        action["updated_at"] = utc_now_iso()
        self._save(action)
        self._publish("action.executed_simulated", action)
        return action

    def _apply_latest_decision(self, action: dict[str, Any], alert: dict[str, Any]) -> dict[str, Any]:
        decision = self.policy_engine.decide(alert)
        action["entity_id"] = str(alert.get("entity_id") or action.get("entity_id") or "unknown")
        action["slice_id"] = self._optional_str(alert.get("slice_id"))
        action["domain"] = self._optional_str(alert.get("domain"))
        action["action_type"] = decision.action_type.value
        action["risk_level"] = decision.risk_level.value
        action["requires_approval"] = decision.requires_approval
        action["status"] = decision.status.value
        action["reason"] = decision.reason
        action["policy_id"] = decision.policy_id
        action["updated_at"] = utc_now_iso()
        return action

    def _save(self, action: dict[str, Any]) -> None:
        action_id = str(action["action_id"])
        self.redis.hset(self._action_key(action_id), mapping=encode_hash(action))
        self.redis.sadd("control:actions:index", action_id)

    def _publish(self, event_type: str, action: dict[str, Any]) -> None:
        publish_event(
            self.redis,
            self.cfg.output_stream,
            event_type=event_type,
            field_name="action",
            payload=action,
            maxlen=self.cfg.stream_maxlen,
        )

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)

    @staticmethod
    def _action_key(action_id: str) -> str:
        return f"control:actions:{action_id}"

    @staticmethod
    def _by_alert_key(alert_id: str) -> str:
        return f"control:actions:by_alert:{alert_id}"
