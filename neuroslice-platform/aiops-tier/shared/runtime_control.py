"""Redis-backed runtime control helpers for Scenario B services."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class RuntimeServiceState:
    service_name: str
    enabled: bool
    mode: str
    updated_at: str | None = None
    updated_by: str | None = None
    reason: str | None = None


def _runtime_key(service_name: str, suffix: str) -> str:
    return f"runtime:service:{service_name}:{suffix}"


def _parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class RuntimeControlGate:
    """Caches Redis runtime flag reads for lightweight per-message checks."""

    def __init__(self, redis_client, service_name: str, refresh_interval_sec: float = 2.0) -> None:
        self.redis = redis_client
        self.service_name = service_name
        self.refresh_interval_sec = max(0.2, float(refresh_interval_sec))
        self._last_refresh_monotonic = 0.0
        self._state = RuntimeServiceState(service_name=service_name, enabled=True, mode="auto")

    def current_state(self) -> RuntimeServiceState:
        now = time.monotonic()
        if now - self._last_refresh_monotonic < self.refresh_interval_sec:
            return self._state

        enabled_raw = self.redis.get(_runtime_key(self.service_name, "enabled"))
        mode_raw = self.redis.get(_runtime_key(self.service_name, "mode"))
        updated_at = self.redis.get(_runtime_key(self.service_name, "updated_at"))
        updated_by = self.redis.get(_runtime_key(self.service_name, "updated_by"))
        reason = self.redis.get(_runtime_key(self.service_name, "reason"))

        enabled = _parse_bool(enabled_raw, default=True)
        mode = str(mode_raw or ("auto" if enabled else "disabled"))
        if mode == "disabled":
            enabled = False

        self._state = RuntimeServiceState(
            service_name=self.service_name,
            enabled=enabled,
            mode=mode,
            updated_at=updated_at,
            updated_by=updated_by,
            reason=reason,
        )
        self._last_refresh_monotonic = now
        return self._state

    def is_enabled(self) -> bool:
        return self.current_state().enabled
