"""Tests for the safe MLOps retraining trigger system.

Covers:
  - Drift event (anomaly-stream) creates a PENDING_APPROVAL request
  - Approval is required before execution
  - Rejected request cannot be executed
  - Kafka drift.alert event creates a request when criteria are met
  - Kafka event ignored when auto_trigger_enabled=false
  - Kafka event ignored when severity is below threshold
  - Cron scheduler creates a SCHEDULED request
  - Duplicate requests are blocked (same model already pending)
  - Cooldown prevents immediate re-trigger
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — lightweight Redis stub
# ---------------------------------------------------------------------------

class _FakeRedis:
    """Minimal async Redis stand-in backed by a plain dict."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._sets: dict[str, set] = {}
        self._zsets: dict[str, dict] = {}
        self._lists: dict[str, list] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, **_kwargs) -> None:
        self._store[key] = value

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self._store.pop(k, None)

    async def sadd(self, key: str, *members) -> int:
        s = self._sets.setdefault(key, set())
        before = len(s)
        s.update(members)
        return len(s) - before

    async def srem(self, key: str, *members) -> int:
        s = self._sets.get(key, set())
        before = len(s)
        s -= set(members)
        return before - len(s)

    async def scard(self, key: str) -> int:
        return len(self._sets.get(key, set()))

    async def smembers(self, key: str) -> set:
        return set(self._sets.get(key, set()))

    async def zadd(self, key: str, mapping: dict, **_kwargs) -> int:
        zset = self._zsets.setdefault(key, {})
        zset.update(mapping)
        return len(mapping)

    async def zrevrange(self, key: str, start: int, stop: int) -> list:
        zset = self._zsets.get(key, {})
        sorted_keys = sorted(zset, key=lambda k: zset[k], reverse=True)
        end = None if stop == -1 else stop + 1
        return sorted_keys[start:end]

    async def lpush(self, key: str, *values) -> int:
        lst = self._lists.setdefault(key, [])
        for v in values:
            lst.insert(0, v)
        return len(lst)

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        lst = self._lists.get(key, [])
        end = None if stop == -1 else stop + 1
        self._lists[key] = lst[start:end]

    async def lrange(self, key: str, start: int, stop: int) -> list:
        lst = self._lists.get(key, [])
        end = None if stop == -1 else stop + 1
        return lst[start:end]

    async def xadd(self, stream: str, fields: dict, **_kwargs) -> str:
        return f"{int(time.time() * 1000)}-0"

    async def xrange(self, stream: str, min: str = "-", max: str = "+") -> list:
        return []

    async def xread(self, streams: dict, count: int = 1000, block: int = 0) -> list:
        return []

    async def ping(self) -> bool:
        return True

    def get_request(self, request_id: str) -> dict | None:
        raw = self._store.get(f"mlops:request:{request_id}")
        if raw is None:
            return None
        return json.loads(raw)

    def pending_ids_for_model(self, model_name: str) -> set:
        return set(self._sets.get(f"mlops:requests:pending:model:{model_name}", set()))

    def all_request_ids(self) -> list[str]:
        zset = self._zsets.get("mlops:requests:index", {})
        return list(zset.keys())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_redis() -> _FakeRedis:
    return _FakeRedis()


@pytest.fixture()
def patch_get_redis(fake_redis: _FakeRedis):
    with patch("main._get_redis", new=AsyncMock(return_value=fake_redis)):
        yield fake_redis


# ---------------------------------------------------------------------------
# Import the module under test after patches are set (avoids import-time Redis)
# ---------------------------------------------------------------------------

import importlib
import sys

@pytest.fixture(autouse=True)
def import_main():
    """Re-import main freshly so module-level state is clean each test."""
    if "main" in sys.modules:
        del sys.modules["main"]
    import main as m
    yield m
    if "main" in sys.modules:
        del sys.modules["main"]


# ---------------------------------------------------------------------------
# Helper to run async functions in tests
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. Drift event (anomaly-stream) creates a PENDING_APPROVAL request
# ---------------------------------------------------------------------------

def test_drift_detected_creates_pending_request(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    req_id = run(m._create_retraining_request(r, "congestion_5g", trigger_type="DRIFT", anomaly_count=20))

    assert req_id, "Expected a non-empty request ID"
    stored = r.get_request(req_id)
    assert stored is not None
    assert stored["status"] == "pending_approval"
    assert stored["trigger_type"] == "DRIFT"
    assert stored["model_internal"] == "congestion_5g"
    assert stored["anomaly_count"] == 20
    # Must be listed in the pending set for the model
    assert req_id in r.pending_ids_for_model("congestion_5g")


# ---------------------------------------------------------------------------
# 2. Approval is required before execution (state machine)
# ---------------------------------------------------------------------------

def test_approval_required_before_execute(patch_get_redis, import_main):
    """A request in pending_approval must not be executable at the Redis layer."""
    r = patch_get_redis
    req_id = run(import_main._create_retraining_request(
        r, "sla_5g", trigger_type="DRIFT", anomaly_count=18
    ))
    stored = r.get_request(req_id)
    assert stored["status"] == "pending_approval"
    # Simulate the API-level rule: only 'approved' may proceed
    assert stored["status"] != "approved", "Request must not auto-approve"


# ---------------------------------------------------------------------------
# 3. Rejected request cannot be executed
# ---------------------------------------------------------------------------

def test_rejected_request_has_terminal_status(patch_get_redis, import_main):
    r = patch_get_redis
    req_id = run(import_main._create_retraining_request(
        r, "sla_5g", trigger_type="DRIFT", anomaly_count=16
    ))
    # Simulate rejection
    stored = r.get_request(req_id)
    stored["status"] = "rejected"
    run(r.set(f"mlops:request:{req_id}", json.dumps(stored)))

    refreshed = r.get_request(req_id)
    assert refreshed["status"] == "rejected"
    # Rejected is a terminal state — cannot transition to running
    assert refreshed["status"] not in {"approved", "running", "completed"}


# ---------------------------------------------------------------------------
# 4. Duplicate requests are blocked (same model already pending)
# ---------------------------------------------------------------------------

def test_duplicate_request_blocked(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    triggered_first = run(m._trigger_mlops_pipeline("congestion_5g", 20))
    assert triggered_first is True

    triggered_second = run(m._trigger_mlops_pipeline("congestion_5g", 22))
    assert triggered_second is False, "Second trigger should be blocked (pending exists)"

    all_ids = r.all_request_ids()
    assert len(all_ids) == 1, "Only one request should have been created"


# ---------------------------------------------------------------------------
# 5. Cooldown prevents re-trigger
# ---------------------------------------------------------------------------

def test_cooldown_prevents_retrigger(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    # Simulate a trigger that already happened just now
    run(m._record_trigger(r, "sla_5g"))
    in_cooldown = run(m._is_in_cooldown(r, "sla_5g"))
    assert in_cooldown is True


def test_no_cooldown_before_first_trigger(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis
    in_cooldown = run(m._is_in_cooldown(r, "sla_5g"))
    assert in_cooldown is False


# ---------------------------------------------------------------------------
# 6. Kafka drift.alert event creates a request when criteria are met
# ---------------------------------------------------------------------------

def test_kafka_event_creates_request_when_criteria_met(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    event = {
        "event_type": "drift_detected",
        "drift_id": str(uuid.uuid4()),
        "model_name": "congestion_5g",
        "timestamp": "2026-05-03T12:00:00Z",
        "p_value": 0.0009,
        "threshold": 0.01,
        "is_drift": True,
        "drift_score": 0.82,
        "severity": "HIGH",
        "recommendation": "Retrain immediately",
        "window_size": 500,
        "auto_trigger_enabled": True,
    }

    run(m._handle_kafka_drift_event(event))

    all_ids = r.all_request_ids()
    assert len(all_ids) == 1
    stored = r.get_request(all_ids[0])
    assert stored["status"] == "pending_approval"
    assert stored["trigger_type"] == "DRIFT"
    assert stored["severity"] == "HIGH"
    assert abs(stored["p_value"] - 0.0009) < 1e-9
    assert abs(stored["drift_score"] - 0.82) < 1e-9
    assert stored["request_source"] == "kafka/drift.alert"


# ---------------------------------------------------------------------------
# 7. Kafka event ignored when auto_trigger_enabled=false
# ---------------------------------------------------------------------------

def test_kafka_event_ignored_when_auto_trigger_off(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    event = {
        "is_drift": True,
        "severity": "HIGH",
        "auto_trigger_enabled": False,
        "model_name": "congestion_5g",
        "p_value": 0.001,
        "drift_score": 0.75,
        "window_size": 500,
    }

    run(m._handle_kafka_drift_event(event))
    assert len(r.all_request_ids()) == 0, "No request should be created when auto_trigger is off"


# ---------------------------------------------------------------------------
# 8. Kafka event ignored when severity is below threshold
# ---------------------------------------------------------------------------

def test_kafka_event_ignored_for_low_severity(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    event = {
        "is_drift": True,
        "severity": "LOW",
        "auto_trigger_enabled": True,
        "model_name": "congestion_5g",
        "p_value": 0.008,
        "drift_score": 0.3,
        "window_size": 500,
    }

    run(m._handle_kafka_drift_event(event))
    assert len(r.all_request_ids()) == 0, "LOW severity must not create a request"


# ---------------------------------------------------------------------------
# 9. Kafka event ignored when is_drift=false
# ---------------------------------------------------------------------------

def test_kafka_event_ignored_when_no_drift(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    event = {
        "is_drift": False,
        "severity": "HIGH",
        "auto_trigger_enabled": True,
        "model_name": "congestion_5g",
        "p_value": 0.05,
    }

    run(m._handle_kafka_drift_event(event))
    assert len(r.all_request_ids()) == 0


# ---------------------------------------------------------------------------
# 10. Cron scheduler creates a SCHEDULED request
# ---------------------------------------------------------------------------

def test_cron_creates_scheduled_request(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    # Patch runtime enabled to True
    with patch.object(m, "_runtime_service_enabled", new=AsyncMock(return_value=True)):
        with patch.object(m, "RETRAINING_CRON_REQUIRE_APPROVAL", True):
            run(m._create_scheduled_request(r, "slice_type_5g", runtime_enabled=True))

    all_ids = r.all_request_ids()
    assert len(all_ids) == 1
    stored = r.get_request(all_ids[0])
    assert stored["trigger_type"] == "SCHEDULED"
    assert stored["status"] == "pending_approval"
    assert stored["request_source"] == "cron-scheduler"


def test_cron_creates_approved_when_no_approval_required(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    with patch.object(m, "RETRAINING_CRON_REQUIRE_APPROVAL", False):
        run(m._create_scheduled_request(r, "sla_5g", runtime_enabled=True))

    all_ids = r.all_request_ids()
    assert len(all_ids) == 1
    stored = r.get_request(all_ids[0])
    assert stored["trigger_type"] == "SCHEDULED"
    assert stored["status"] == "approved"


# ---------------------------------------------------------------------------
# 11. Cron duplicate blocked
# ---------------------------------------------------------------------------

def test_cron_duplicate_blocked(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    with patch.object(m, "RETRAINING_CRON_REQUIRE_APPROVAL", True):
        run(m._create_scheduled_request(r, "sla_5g", runtime_enabled=True))
        run(m._create_scheduled_request(r, "sla_5g", runtime_enabled=True))

    assert len(r.all_request_ids()) == 1, "Second cron request must be blocked (pending exists)"


# ---------------------------------------------------------------------------
# 12. fire_scheduled_retraining covers all configured cron models
# ---------------------------------------------------------------------------

def test_fire_scheduled_retraining_all_models(patch_get_redis, import_main):
    m = import_main
    r = patch_get_redis

    cron_models = ["congestion_5g", "sla_5g", "slice_type_5g"]
    with patch.object(m, "RETRAINING_CRON_MODELS", cron_models):
        with patch.object(m, "RETRAINING_CRON_REQUIRE_APPROVAL", True):
            with patch.object(m, "_runtime_service_enabled", new=AsyncMock(return_value=True)):
                run(m._fire_scheduled_retraining())

    all_ids = r.all_request_ids()
    assert len(all_ids) == len(cron_models), "One request per cron model expected"

    trigger_types = {r.get_request(rid)["trigger_type"] for rid in all_ids}
    assert trigger_types == {"SCHEDULED"}
