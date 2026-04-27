"""Redis Stream consumer for AIOps events."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis

from .alert_store import AlertStore
from .config import AlertManagementConfig
from .redis_client import ack_message, ensure_consumer_group, read_group
from .schemas import Alert, AlertSeverity, AlertType

logger = logging.getLogger(__name__)

SEVERITY_BY_NUMBER = {
    0: AlertSeverity.LOW,
    1: AlertSeverity.LOW,
    2: AlertSeverity.MEDIUM,
    3: AlertSeverity.HIGH,
    4: AlertSeverity.CRITICAL,
}


class AlertConsumer:
    def __init__(self, cfg: AlertManagementConfig, redis_client: redis.Redis, store: AlertStore) -> None:
        self.cfg = cfg
        self.redis = redis_client
        self.store = store
        self._running = True

    def stop(self) -> None:
        self._running = False

    async def run_forever(self) -> None:
        for stream in self.cfg.input_streams:
            ensure_consumer_group(self.redis, stream, self.cfg.consumer_group)

        logger.info(
            "Consuming AIOps streams=%s group=%s consumer=%s",
            ",".join(self.cfg.input_streams),
            self.cfg.consumer_group,
            self.cfg.consumer_name,
        )

        while self._running:
            try:
                messages = read_group(
                    self.redis,
                    self.cfg.input_streams,
                    self.cfg.consumer_group,
                    self.cfg.consumer_name,
                    count=self.cfg.read_count,
                    block_ms=self.cfg.block_ms,
                )
                if not messages:
                    await asyncio.sleep(0.05)
                    continue

                for stream, msg_id, fields in messages:
                    try:
                        payload = self._extract_payload(fields)
                        alert = self._build_alert(stream, payload)
                        if alert is not None:
                            self.store.upsert_from_event(alert)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to process %s:%s: %s", stream, msg_id, exc)
                    finally:
                        ack_message(self.redis, stream, self.cfg.consumer_group, msg_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("Alert consumer loop error: %s", exc)
                await asyncio.sleep(1.0)

    @staticmethod
    def _extract_payload(fields: dict[str, Any]) -> dict[str, Any]:
        raw = fields.get("event") or fields.get("payload") or fields.get("alert")
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

    def _build_alert(self, stream: str, payload: dict[str, Any]) -> Alert | None:
        explicit_type = self._get(payload, "alert_type", "alertType")
        alert_type = self._alert_type(stream, explicit_type)
        if self._is_benign(payload, explicit_type):
            return None

        severity = self._severity(payload)
        entity_id = str(self._get(payload, "entity_id", "entityId", "node_id", "nodeId") or "unknown")
        source = str(self._get(payload, "source", "service") or stream)
        dedup_key = "|".join([entity_id, alert_type.value, source])
        summary = str(
            self._get(payload, "summary", "message")
            or self._default_summary(alert_type=alert_type, severity=severity, entity_id=entity_id)
        )

        return Alert(
            dedup_key=dedup_key,
            entity_id=entity_id,
            slice_id=self._optional_str(self._get(payload, "slice_id", "sliceId")),
            domain=self._optional_str(self._get(payload, "domain")),
            alert_type=alert_type,
            severity=severity,
            source=source,
            summary=summary,
            evidence=payload,
        )

    @staticmethod
    def _alert_type(stream: str, explicit_type: Any) -> AlertType:
        if explicit_type:
            normalized = str(explicit_type).strip().upper()
            if normalized in AlertType.__members__:
                return AlertType(normalized)
            if normalized in {"ANOMALY", "CONGESTION_ANOMALY"}:
                return AlertType.CONGESTION
            if normalized in {"SLA", "SLA_AT_RISK"}:
                return AlertType.SLA_RISK
            if normalized in {"SLICE", "MISMATCH"}:
                return AlertType.SLICE_MISMATCH
            if normalized in {"FAULT", "FAULTS"}:
                return AlertType.FAULT_EVENT
            return AlertType.UNKNOWN

        if stream == "events.anomaly":
            return AlertType.CONGESTION
        if stream == "events.sla":
            return AlertType.SLA_RISK
        if stream == "events.slice.classification":
            return AlertType.SLICE_MISMATCH
        return AlertType.UNKNOWN

    def _is_benign(self, payload: dict[str, Any], explicit_type: Any) -> bool:
        if explicit_type:
            return False

        prediction = str(self._get(payload, "prediction") or "").strip().lower()
        if prediction in {"normal", "sla_stable"}:
            return True

        severity = self._get(payload, "severity")
        if self._as_float(severity, default=None) == 0.0:
            return True

        details = self._get(payload, "details")
        if isinstance(details, dict) and details.get("mismatch") is False:
            return True

        return False

    def _severity(self, payload: dict[str, Any]) -> AlertSeverity:
        raw = self._get(payload, "severity")
        if raw is not None:
            if isinstance(raw, str):
                normalized = raw.strip().upper()
                if normalized in AlertSeverity.__members__:
                    return AlertSeverity(normalized)
                numeric = self._as_float(raw, default=None)
            else:
                numeric = self._as_float(raw, default=None)
            if numeric is not None:
                return SEVERITY_BY_NUMBER.get(int(numeric), self._severity_from_score(float(numeric)))

        score = self._first_numeric(payload, "score", "risk_score", "riskScore", "confidence")
        if score is not None:
            return self._severity_from_score(score)
        return AlertSeverity.LOW

    @staticmethod
    def _severity_from_score(score: float) -> AlertSeverity:
        if score >= 0.85:
            return AlertSeverity.CRITICAL
        if score >= 0.70:
            return AlertSeverity.HIGH
        if score >= 0.50:
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW

    def _first_numeric(self, payload: dict[str, Any], *names: str) -> float | None:
        for name in names:
            value = self._get(payload, name)
            parsed = self._as_float(value, default=None)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _get(payload: dict[str, Any], *names: str) -> Any:
        for name in names:
            if name in payload:
                return payload[name]
        return None

    @staticmethod
    def _as_float(value: Any, default: float | None = 0.0) -> float | None:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)

    @staticmethod
    def _default_summary(*, alert_type: AlertType, severity: AlertSeverity, entity_id: str) -> str:
        return f"{severity.value} {alert_type.value} alert for {entity_id}"
