from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from typing import Any

import pytest

import main


class _FakeLock:
    def acquire(self, blocking: bool = True) -> bool:  # noqa: ARG002
        return True

    def release(self) -> None:
        return None


class _FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.zsets: dict[str, dict[str, float]] = {}

    def get(self, key: str) -> str | None:
        return self.kv.get(key)

    def set(self, key: str, value: Any, ex: int | None = None, nx: bool = False) -> bool:  # noqa: ARG002
        if nx and key in self.kv:
            return False
        self.kv[key] = str(value)
        return True

    def delete(self, key: str) -> int:
        removed = 0
        if key in self.kv:
            del self.kv[key]
            removed += 1
        if key in self.sets:
            del self.sets[key]
            removed += 1
        if key in self.zsets:
            del self.zsets[key]
            removed += 1
        return removed

    def sadd(self, key: str, *members: str) -> int:
        bucket = self.sets.setdefault(key, set())
        before = len(bucket)
        for member in members:
            bucket.add(str(member))
        return len(bucket) - before

    def srem(self, key: str, *members: str) -> int:
        bucket = self.sets.setdefault(key, set())
        removed = 0
        for member in members:
            if str(member) in bucket:
                bucket.remove(str(member))
                removed += 1
        return removed

    def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    def scard(self, key: str) -> int:
        return len(self.sets.get(key, set()))

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        bucket = self.zsets.setdefault(key, {})
        for member, score in mapping.items():
            bucket[str(member)] = float(score)
        return len(mapping)

    def zrevrange(self, key: str, start: int, stop: int) -> list[str]:
        bucket = self.zsets.get(key, {})
        ordered = sorted(bucket.items(), key=lambda x: x[1], reverse=True)
        if stop < 0:
            stop = len(ordered) - 1
        return [member for member, _score in ordered[start: stop + 1]]

    def keys(self, pattern: str) -> list[str]:
        result: list[str] = []
        for key in self.kv.keys():
            if fnmatch(key, pattern):
                result.append(key)
        for key in self.sets.keys():
            if fnmatch(key, pattern):
                result.append(key)
        return sorted(set(result))

    def lock(self, _name: str, timeout: int, blocking_timeout: int) -> _FakeLock:  # noqa: ARG002
        return _FakeLock()


def _request_payload(request_id: str, *, status: str = "approved", created_at: str | None = None) -> dict[str, Any]:
    now = created_at or datetime.now(UTC).isoformat()
    return {
        "id": request_id,
        "model": "congestion-5g",
        "model_internal": "congestion_5g",
        "pipeline_action": "pipeline_congestion_5g",
        "trigger_type": "SCHEDULED",
        "reason": "scheduled",
        "anomaly_count": 0,
        "threshold": 0,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "auto_execute": False,
    }


def _seed_pending(fake: _FakeRedis, request_id: str, *, status: str = "approved", created_at: str | None = None) -> None:
    payload = _request_payload(request_id, status=status, created_at=created_at)
    fake.set(main._request_key(request_id), json.dumps(payload))
    fake.sadd(main._request_pending_key("congestion_5g"), request_id)
    marker = {
        "request_id": request_id,
        "model_name": "congestion_5g",
        "created_at": payload["created_at"],
        "created_at_epoch": main._safe_iso_to_ts(payload["created_at"]) or time.time(),
        "expires_at_epoch": time.time() + 3600,
        "owner": "test",
        "source": "test",
    }
    fake.set(main._pending_request_key(request_id), json.dumps(marker))
    fake.set(main._pending_model_lease_key("congestion_5g"), json.dumps(marker))


def _patch_runtime_redis(monkeypatch: pytest.MonkeyPatch, fake: _FakeRedis) -> None:
    monkeypatch.setattr(main, "_runtime_redis_client", lambda: fake)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return dict(self._payload)


def _patch_http_client(monkeypatch: pytest.MonkeyPatch, *, response: _FakeResponse | None = None, exc: Exception | None = None) -> None:
    class _Client:
        def __init__(self, timeout: int):  # noqa: ARG002
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ARG002
            return False

        def post(self, url: str, json: dict[str, Any], headers: dict[str, str]):  # noqa: ARG002
            if exc is not None:
                raise exc
            assert response is not None
            return response

    monkeypatch.setattr(main.httpx, "Client", _Client)


def test_completed_request_clears_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    _seed_pending(fake, "req-completed", status="running")
    _patch_runtime_redis(monkeypatch, fake)
    _patch_http_client(monkeypatch, response=_FakeResponse(200, {"accepted": True, "exit_code": 0, "timed_out": False}))

    main._execute_retraining_request_background("req-completed")

    payload = json.loads(fake.get(main._request_key("req-completed")) or "{}")
    assert payload["status"] == "completed"
    assert "req-completed" not in fake.smembers(main._request_pending_key("congestion_5g"))


def test_failed_request_clears_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    _seed_pending(fake, "req-failed", status="running")
    _patch_runtime_redis(monkeypatch, fake)
    _patch_http_client(monkeypatch, response=_FakeResponse(200, {"accepted": True, "exit_code": 9, "timed_out": False}))

    main._execute_retraining_request_background("req-failed")

    payload = json.loads(fake.get(main._request_key("req-failed")) or "{}")
    assert payload["status"] == "failed"
    assert "req-failed" not in fake.smembers(main._request_pending_key("congestion_5g"))


def test_timeout_request_clears_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    _seed_pending(fake, "req-timeout", status="running")
    _patch_runtime_redis(monkeypatch, fake)
    _patch_http_client(monkeypatch, response=_FakeResponse(200, {"accepted": True, "exit_code": None, "timed_out": True}))

    main._execute_retraining_request_background("req-timeout")

    payload = json.loads(fake.get(main._request_key("req-timeout")) or "{}")
    assert payload["status"] == "timeout"
    assert "req-timeout" not in fake.smembers(main._request_pending_key("congestion_5g"))


def test_exception_during_execution_clears_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    _seed_pending(fake, "req-exc", status="running")
    _patch_runtime_redis(monkeypatch, fake)
    _patch_http_client(monkeypatch, exc=RuntimeError("boom"))

    main._execute_retraining_request_background("req-exc")

    payload = json.loads(fake.get(main._request_key("req-exc")) or "{}")
    assert payload["status"] == "failed"
    assert "req-exc" not in fake.smembers(main._request_pending_key("congestion_5g"))


def test_skipped_request_clears_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    request_id = "req-skipped"
    payload = _request_payload(request_id, status="approved")
    fake.set(main._request_key(request_id), json.dumps(payload))
    _seed_pending(fake, request_id, status="approved")
    _patch_runtime_redis(monkeypatch, fake)

    fake.set(main._request_cooldown_key("congestion-5g"), str(time.time()))
    result = main._attempt_execute_retraining_request(
        fake,
        request_id,
        executed_by="tester",
        launch_background=lambda _: None,
    )

    assert result.status == "skipped"
    assert request_id not in fake.smembers(main._request_pending_key("congestion_5g"))


def test_stale_pending_marker_is_removed() -> None:
    fake = _FakeRedis()
    stale_created = (datetime.now(UTC) - timedelta(seconds=main._MLOPS_PENDING_TTL_SECONDS + 10)).isoformat()
    _seed_pending(fake, "req-stale", status="approved", created_at=stale_created)

    has_live = main._has_live_pending_request(fake, "congestion_5g")

    payload = json.loads(fake.get(main._request_key("req-stale")) or "{}")
    assert has_live is False
    assert payload["status"] == "expired"
    assert "req-stale" not in fake.smembers(main._request_pending_key("congestion_5g"))


def test_cleanup_is_idempotent() -> None:
    fake = _FakeRedis()
    _seed_pending(fake, "req-idempotent", status="rejected")

    main.clear_pending_retraining(
        fake,
        model_name="congestion_5g",
        request_id="req-idempotent",
        reason="test_first",
        request_status="rejected",
    )
    main.clear_pending_retraining(
        fake,
        model_name="congestion_5g",
        request_id="req-idempotent",
        reason="test_second",
        request_status="rejected",
    )

    assert "req-idempotent" not in fake.smembers(main._request_pending_key("congestion_5g"))


def test_scheduler_can_create_request_after_stale_cleanup() -> None:
    fake = _FakeRedis()
    stale_created = (datetime.now(UTC) - timedelta(seconds=main._MLOPS_PENDING_TTL_SECONDS + 60)).isoformat()
    _seed_pending(fake, "req-old", status="approved", created_at=stale_created)

    assert main._has_live_pending_request(fake, "congestion_5g") is False
    new_req = main._create_scheduled_retraining_request(
        fake,
        model_name_public="congestion-5g",
        require_approval=True,
        source_schedule_id="s1",
    )

    assert new_req in fake.smembers(main._request_pending_key("congestion_5g"))


def test_cleanup_does_not_remove_different_active_lease_when_not_stale() -> None:
    fake = _FakeRedis()
    _seed_pending(fake, "req-active", status="approved")
    other_marker = {
        "request_id": "req-active",
        "model_name": "congestion_5g",
        "created_at": datetime.now(UTC).isoformat(),
        "created_at_epoch": time.time(),
        "expires_at_epoch": time.time() + 3600,
        "owner": "test",
        "source": "test",
    }
    fake.set(main._pending_model_lease_key("congestion_5g"), json.dumps(other_marker))

    main.clear_pending_retraining(
        fake,
        model_name="congestion_5g",
        request_id="req-other",
        reason="mismatch",
        request_status="approved",
    )

    lease = json.loads(fake.get(main._pending_model_lease_key("congestion_5g")) or "{}")
    assert lease.get("request_id") == "req-active"


def test_pending_dedupe_is_scoped_by_trigger_type() -> None:
    fake = _FakeRedis()
    _seed_pending(fake, "req-drift", status="approved")
    drift_req = json.loads(fake.get(main._request_key("req-drift")) or "{}")
    drift_req["trigger_type"] = "DRIFT"
    fake.set(main._request_key("req-drift"), json.dumps(drift_req))

    assert main._has_live_pending_request(fake, "congestion_5g", trigger_type="DRIFT") is True
    assert main._has_live_pending_request(fake, "congestion_5g", trigger_type="SCHEDULED") is False
