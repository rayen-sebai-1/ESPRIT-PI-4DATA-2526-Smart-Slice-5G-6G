"""Redis-backed alert persistence and lifecycle operations."""
from __future__ import annotations

from typing import Any

import redis

from .config import AlertManagementConfig
from .redis_client import decode_hash, encode_hash, publish_event
from .schemas import Alert, AlertStatus, utc_now_iso


class AlertStore:
    def __init__(self, cfg: AlertManagementConfig, redis_client: redis.Redis) -> None:
        self.cfg = cfg
        self.redis = redis_client

    def list_alerts(self) -> list[dict[str, Any]]:
        alert_ids = list(self.redis.smembers("control:alerts:index"))
        alerts = [alert for alert_id in alert_ids if (alert := self.get_alert(alert_id)) is not None]
        alerts.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        return alerts

    def get_alert(self, alert_id: str) -> dict[str, Any] | None:
        raw = self.redis.hgetall(self._alert_key(alert_id))
        if not raw:
            return None
        return decode_hash(raw)

    def upsert_from_event(self, alert: Alert) -> tuple[dict[str, Any], str]:
        existing = self._find_unresolved_by_dedup_key(alert.dedup_key)
        if existing is None:
            data = alert.model_dump(mode="json")
            self._save(data)
            self.redis.set(self._dedup_key(alert.dedup_key), alert.alert_id)
            self._publish("alert.created", data)
            return data, "alert.created"

        existing["slice_id"] = alert.slice_id or existing.get("slice_id")
        existing["domain"] = alert.domain or existing.get("domain")
        existing["severity"] = alert.severity.value
        existing["summary"] = alert.summary
        existing["source"] = alert.source
        existing["evidence"] = alert.evidence
        existing["event_count"] = int(existing.get("event_count") or 0) + 1
        existing["updated_at"] = utc_now_iso()
        self._save(existing)
        self._publish("alert.updated", existing)
        return existing, "alert.updated"

    def acknowledge(self, alert_id: str) -> dict[str, Any] | None:
        alert = self.get_alert(alert_id)
        if alert is None:
            return None
        if alert.get("status") == AlertStatus.RESOLVED.value:
            raise ValueError("Resolved alerts cannot be acknowledged.")
        alert["status"] = AlertStatus.ACKNOWLEDGED.value
        alert["updated_at"] = utc_now_iso()
        self._save(alert)
        self._publish("alert.acknowledged", alert)
        return alert

    def resolve(self, alert_id: str) -> dict[str, Any] | None:
        alert = self.get_alert(alert_id)
        if alert is None:
            return None
        if alert.get("status") == AlertStatus.RESOLVED.value:
            raise ValueError("Alert is already resolved.")
        alert["status"] = AlertStatus.RESOLVED.value
        alert["updated_at"] = utc_now_iso()
        self._save(alert)
        self.redis.delete(self._dedup_key(str(alert.get("dedup_key"))))
        self._publish("alert.resolved", alert)
        return alert

    def _find_unresolved_by_dedup_key(self, dedup_key: str) -> dict[str, Any] | None:
        alert_id = self.redis.get(self._dedup_key(dedup_key))
        if not alert_id:
            return None

        alert = self.get_alert(alert_id)
        if alert is None:
            self.redis.delete(self._dedup_key(dedup_key))
            return None

        if alert.get("status") in {AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value}:
            return alert

        self.redis.delete(self._dedup_key(dedup_key))
        return None

    def _save(self, alert: dict[str, Any]) -> None:
        alert_id = str(alert["alert_id"])
        self.redis.hset(self._alert_key(alert_id), mapping=encode_hash(alert))
        self.redis.sadd("control:alerts:index", alert_id)

    def _publish(self, event_type: str, alert: dict[str, Any]) -> None:
        publish_event(
            self.redis,
            self.cfg.output_stream,
            event_type=event_type,
            field_name="alert",
            payload=alert,
            maxlen=self.cfg.stream_maxlen,
        )

    @staticmethod
    def _alert_key(alert_id: str) -> str:
        return f"control:alerts:{alert_id}"

    @staticmethod
    def _dedup_key(dedup_key: str) -> str:
        return f"control:alerts:dedup:{dedup_key}"
