from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .telemetry_summary import empty_telemetry_summary, summarize_telemetry_records

try:  # pragma: no cover - exercised in container images
    from influxdb_client import InfluxDBClient
except Exception:  # pragma: no cover - dependency is optional for smoke tests
    InfluxDBClient = None  # type: ignore

try:  # pragma: no cover - exercised in container images
    import redis as redis_lib
except Exception:  # pragma: no cover - dependency is optional for smoke tests
    redis_lib = None  # type: ignore


logger = logging.getLogger(__name__)

DEFAULT_TIME_RANGE = {"start": "-30m", "stop": "now()"}
LOCAL_DEV_INFLUX_TOKEN = "neuroslice_token_12345"

VALID_DOMAINS = {"core", "edge", "ran"}
VALID_ENTITY_TYPES = {"amf", "smf", "upf", "edge_upf", "mec_app", "compute_node", "gnb", "cell"}
VALID_SLICE_TYPES = {"eMBB", "URLLC", "mMTC"}

SCALAR_REDIS_KEYS = (
    "ran:congestion_score",
    "core:active_ues",
    "edge:saturation",
    "edge:misrouting_ratio",
)

AIOPS_PREFIXES = {
    "congestion": "aiops:congestion",
    "slice_classification": "aiops:slice_classification",
    "sla": "aiops:sla",
}

EVENT_STREAMS = {
    "anomaly": "events.anomaly",
    "slice_classification": "events.slice.classification",
    "sla": "events.sla",
}


class InfluxTelemetryClient:
    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        org: Optional[str] = None,
        bucket: Optional[str] = None,
        timeout_ms: int = 10_000,
    ) -> None:
        self.url = url or os.getenv("INFLUXDB_URL", "http://influxdb:8086")
        self.token = token or os.getenv("INFLUXDB_TOKEN") or LOCAL_DEV_INFLUX_TOKEN
        self.org = org or os.getenv("INFLUXDB_ORG", "neuroslice")
        self.bucket = bucket or os.getenv("INFLUXDB_BUCKET", "telemetry")
        self.timeout_ms = timeout_ms

    def fetch_kpis(
        self,
        slice_id: str = "",
        time_range: Any = None,
        domain: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        slice_type: Optional[str] = None,
        query_parameters: Any = None,
    ) -> Dict[str, Any]:
        filters, warnings = normalize_filters(
            slice_id=slice_id,
            domain=domain,
            entity_id=entity_id,
            entity_type=entity_type,
            slice_type=slice_type,
            query_parameters=query_parameters,
        )
        normalized_time_range = normalize_time_range(time_range, query_parameters=query_parameters)

        if InfluxDBClient is None:
            return self._error_payload(
                message="influxdb-client is not installed in this environment.",
                time_range=normalized_time_range,
                filters=filters,
                warnings=warnings,
            )

        rows: List[Dict[str, Any]] = []
        faults: Dict[str, Any] = {
            "status": "not_queried",
            "active_faults": [],
            "recent_faults": [],
            "recently_cleared": [],
            "aggregate_counts": [],
            "redis_active_faults": [],
        }

        client = None
        try:
            client = InfluxDBClient(url=self.url, token=self.token, org=self.org, timeout=self.timeout_ms)
            tables = client.query_api().query(org=self.org, query=self._build_telemetry_flux(filters, normalized_time_range))
            rows = self._records_from_tables(tables)
            entity_ids = sorted({str(row["entity_id"]) for row in rows if row.get("entity_id")})[:25]
            faults = self.fetch_faults(
                time_range=normalized_time_range,
                slice_id=str(filters.get("slice_id") or ""),
                entity_ids=entity_ids,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Influx telemetry query failed: %s", _scrub_secret(str(exc), self.token))
            return self._error_payload(
                message=_scrub_secret(str(exc), self.token),
                time_range=normalized_time_range,
                filters=filters,
                warnings=warnings,
            )
        finally:
            if client is not None:
                client.close()

        telemetry = summarize_telemetry_records(
            rows,
            time_range=normalized_time_range,
            filters=filters,
        )
        if warnings:
            telemetry["warnings"] = warnings

        return {
            "status": "ok" if telemetry.get("status") == "ok" else "no_data",
            "source": "influxdb",
            "org": self.org,
            "bucket": self.bucket,
            "query": {
                "time_range": normalized_time_range,
                "filters": filters,
            },
            "telemetry": telemetry,
            "faults": faults,
        }

    def fetch_faults(
        self,
        time_range: Optional[Dict[str, str]] = None,
        slice_id: str = "",
        entity_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        normalized_time_range = time_range or DEFAULT_TIME_RANGE
        effective_entity_ids = [str(item) for item in (entity_ids or []) if str(item).strip()]
        redis_faults = RedisStateClient().read_active_faults(slice_id=slice_id, entity_ids=effective_entity_ids)

        if InfluxDBClient is None:
            return {
                "status": "error",
                "source": "influxdb",
                "message": "influxdb-client is not installed in this environment.",
                "active_faults": [],
                "recent_faults": [],
                "recently_cleared": [],
                "aggregate_counts": [],
                "redis_active_faults": redis_faults,
            }

        client = None
        try:
            client = InfluxDBClient(url=self.url, token=self.token, org=self.org, timeout=self.timeout_ms)
            tables = client.query_api().query(org=self.org, query=self._build_fault_flux(normalized_time_range))
            records = self._fault_records_from_tables(tables)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Influx faults query failed: %s", _scrub_secret(str(exc), self.token))
            return {
                "status": "error",
                "source": "influxdb",
                "message": _scrub_secret(str(exc), self.token),
                "active_faults": [],
                "recent_faults": [],
                "recently_cleared": [],
                "aggregate_counts": [],
                "redis_active_faults": redis_faults,
            }
        finally:
            if client is not None:
                client.close()

        filtered = [record for record in records if _fault_matches(record, slice_id, effective_entity_ids)]
        aggregate_counts = [
            record
            for record in records
            if record.get("type") == "aggregate"
        ][-10:]
        active_faults = [record for record in filtered if _truthy(record.get("active"))]
        recently_cleared = [record for record in filtered if record.get("active") is not None and not _truthy(record.get("active"))]

        return {
            "status": "ok" if records or redis_faults else "no_data",
            "source": "influxdb",
            "measurement": "faults",
            "time_range": normalized_time_range,
            "filters": {
                "slice_id": slice_id or None,
                "entity_ids": effective_entity_ids,
            },
            "active_faults": active_faults[-25:],
            "recent_faults": filtered[-25:],
            "recently_cleared": recently_cleared[-10:],
            "aggregate_counts": aggregate_counts,
            "redis_active_faults": redis_faults,
        }

    def _build_telemetry_flux(self, filters: Dict[str, Any], time_range: Dict[str, str]) -> str:
        filter_lines = [
            '  |> filter(fn: (r) => r._measurement == "telemetry")',
            '  |> filter(fn: (r) => strings.hasPrefix(v: r._field, prefix: "kpi_") or strings.hasPrefix(v: r._field, prefix: "derived_") or r._field == "severity")',
        ]
        for tag in ("slice_id", "domain", "entity_id", "entity_type", "slice_type"):
            value = filters.get(tag)
            if not value:
                continue
            if tag == "slice_id":
                variants = _slice_id_variants(value)
                if variants:
                    checks = " or ".join(
                        f'strings.toLower(v: r.slice_id) == "{_flux_escape(candidate)}"'
                        for candidate in variants
                    )
                    filter_lines.append(f"  |> filter(fn: (r) => exists r.slice_id and ({checks}))")
                continue

            escaped = _flux_escape(str(value).strip().lower())
            filter_lines.append(
                f'  |> filter(fn: (r) => exists r.{tag} and strings.toLower(v: r.{tag}) == "{escaped}")'
            )

        return "\n".join(
            [
                'import "strings"',
                f'from(bucket: "{_flux_escape(self.bucket)}")',
                f"  |> range(start: {_flux_time(time_range.get('start'))}, stop: {_flux_time(time_range.get('stop'))})",
                *filter_lines,
            ]
        )

    def _build_fault_flux(self, time_range: Dict[str, str]) -> str:
        return "\n".join(
            [
                f'from(bucket: "{_flux_escape(self.bucket)}")',
                f"  |> range(start: {_flux_time(time_range.get('start'))}, stop: {_flux_time(time_range.get('stop'))})",
                '  |> filter(fn: (r) => r._measurement == "faults")',
                '  |> filter(fn: (r) => r._field == "active_count" or r._field == "severity" or r._field == "active")',
            ]
        )

    @staticmethod
    def _records_from_tables(tables: Iterable[Any]) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for table in tables:
            for record in getattr(table, "records", []):
                values = getattr(record, "values", {}) or {}
                records.append(
                    {
                        "timestamp": _timestamp_to_string(record.get_time()),
                        "slice_id": _clean_tag(values.get("slice_id")),
                        "domain": _clean_tag(values.get("domain")),
                        "entity_id": _clean_tag(values.get("entity_id")),
                        "entity_type": _clean_tag(values.get("entity_type")),
                        "slice_type": _clean_tag(values.get("slice_type")),
                        "field": record.get_field(),
                        "value": _coerce_numeric(record.get_value()),
                    }
                )
        return records

    @staticmethod
    def _fault_records_from_tables(tables: Iterable[Any]) -> List[Dict[str, Any]]:
        grouped: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        for table in tables:
            for record in getattr(table, "records", []):
                values = getattr(record, "values", {}) or {}
                timestamp = _timestamp_to_string(record.get_time())
                key = (
                    timestamp,
                    values.get("type"),
                    values.get("fault_id"),
                    values.get("fault_type"),
                    values.get("scenario_id"),
                    values.get("affected_entities"),
                )
                item = grouped.setdefault(
                    key,
                    {
                        "timestamp": timestamp,
                        "type": _clean_tag(values.get("type")),
                        "fault_id": _clean_tag(values.get("fault_id")),
                        "fault_type": _clean_tag(values.get("fault_type")),
                        "scenario_id": _clean_tag(values.get("scenario_id")),
                        "affected_entities": _split_entities(values.get("affected_entities")),
                    },
                )
                field = str(record.get_field() or "")
                if field:
                    item[field] = _coerce_numeric(record.get_value())

        return sorted(grouped.values(), key=lambda item: str(item.get("timestamp") or ""))

    def _error_payload(
        self,
        message: str,
        time_range: Dict[str, str],
        filters: Dict[str, Any],
        warnings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        telemetry = empty_telemetry_summary(time_range=time_range, filters=filters, note="InfluxDB query failed.")
        if warnings:
            telemetry["warnings"] = warnings
        return {
            "status": "error",
            "source": "influxdb",
            "org": self.org,
            "bucket": self.bucket,
            "query": {
                "time_range": time_range,
                "filters": filters,
            },
            "error": {
                "message": message or "InfluxDB query failed.",
            },
            "telemetry": telemetry,
            "faults": {
                "status": "unknown",
                "active_faults": [],
                "recent_faults": [],
                "recently_cleared": [],
                "aggregate_counts": [],
                "redis_active_faults": [],
            },
        }


class RedisStateClient:
    def __init__(
        self,
        redis_url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        socket_timeout: float = 2.0,
    ) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.host = host or os.getenv("REDIS_HOST", "redis")
        self.port = int(port if port is not None else os.getenv("REDIS_PORT", "6379"))
        self.db = int(db if db is not None else os.getenv("REDIS_DB", "0"))
        self.socket_timeout = socket_timeout

    def fetch_state(
        self,
        slice_id: str = "",
        entity_ids: Optional[Sequence[str]] = None,
        query_parameters: Any = None,
    ) -> Dict[str, Any]:
        filters, warnings = normalize_filters(slice_id=slice_id, query_parameters=query_parameters)
        normalized_slice_id = str(filters.get("slice_id") or "").strip()
        requested_entity_ids = _normalize_entity_ids(entity_ids or _extract_entity_ids(query_parameters))

        if redis_lib is None:
            return self._error_payload(
                slice_id=normalized_slice_id,
                entity_ids=requested_entity_ids,
                message="redis package is not installed in this environment.",
                warnings=warnings,
            )

        try:
            redis_client = self._connect()
            redis_client.ping()

            discovered_entity_ids = requested_entity_ids
            if not discovered_entity_ids:
                discovered_entity_ids = self._discover_entities_from_stream(redis_client, normalized_slice_id)

            active_faults = self.read_active_faults(
                slice_id=normalized_slice_id,
                entity_ids=discovered_entity_ids,
                redis_client=redis_client,
            )
            if not discovered_entity_ids:
                discovered_entity_ids = _entities_from_faults(active_faults)

            entities = self._read_entities(redis_client, discovered_entity_ids)
            aiops = self._read_aiops(redis_client, discovered_entity_ids)
            recent_events = self._read_recent_events(redis_client, normalized_slice_id, discovered_entity_ids)
            cross_domain = self._read_cross_domain(redis_client)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Redis state query failed: %s", str(exc))
            return self._error_payload(
                slice_id=normalized_slice_id,
                entity_ids=requested_entity_ids,
                message=str(exc),
                warnings=warnings,
            )

        payload = {
            "status": "ok",
            "source": "redis",
            "slice_id": normalized_slice_id or None,
            "entity_ids": discovered_entity_ids,
            "active_faults": active_faults,
            "entities": entities,
            "aiops": aiops,
            "cross_domain": cross_domain,
            "recent_events": recent_events,
        }
        if warnings:
            payload["warnings"] = warnings
        return payload

    def read_active_faults(
        self,
        slice_id: str = "",
        entity_ids: Optional[Sequence[str]] = None,
        redis_client: Any = None,
    ) -> List[Dict[str, Any]]:
        effective_entity_ids = _normalize_entity_ids(entity_ids)

        if redis_lib is None:
            return []

        client = redis_client
        try:
            if client is None:
                client = self._connect()
                client.ping()
            raw = client.hgetall("faults:active")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read Redis faults:active: %s", exc)
            return []

        faults = []
        for fault_id, value in (raw or {}).items():
            decoded = decode_redis_value(value)
            if not isinstance(decoded, dict):
                decoded = {"raw": decoded}
            decoded.setdefault("fault_id", fault_id)
            decoded["affected_entities"] = _split_entities(decoded.get("affected_entities"))
            if _fault_matches(decoded, slice_id, effective_entity_ids):
                faults.append(_compact_fault(decoded))

        faults.sort(key=lambda item: str(item.get("activated_at") or item.get("start_time") or ""))
        return faults[-25:]

    def _connect(self) -> Any:
        if self.redis_url:
            return redis_lib.Redis.from_url(  # type: ignore[union-attr]
                self.redis_url,
                decode_responses=True,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.socket_timeout,
            )
        return redis_lib.Redis(  # type: ignore[union-attr]
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=True,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_timeout,
        )

    def _discover_entities_from_stream(self, redis_client: Any, slice_id: str, count: int = 1200) -> List[str]:
        normalized_slice_id = _normalize_token(slice_id)
        if not normalized_slice_id:
            return []

        entity_ids: List[str] = []
        for _, fields in _xrevrange(redis_client, "stream:norm.telemetry", count=count):
            event = _extract_stream_event(fields)
            if not isinstance(event, dict):
                continue
            event_slice_id = event.get("sliceId") or event.get("slice_id")
            if not _slice_id_matches(event_slice_id, normalized_slice_id):
                continue
            entity_id = event.get("entityId") or event.get("entity_id")
            if entity_id and str(entity_id) not in entity_ids:
                entity_ids.append(str(entity_id))
            if len(entity_ids) >= 25:
                break

        if entity_ids:
            return entity_ids

        return self._scan_entity_hashes(redis_client, normalized_slice_id)

    def _scan_entity_hashes(self, redis_client: Any, slice_id: str, limit: int = 25) -> List[str]:
        entity_ids: List[str] = []
        normalized_slice_id = _normalize_token(slice_id)
        try:
            iterator = redis_client.scan_iter(match="entity:*", count=100)
            for key in iterator:
                entity_id = str(key).replace("entity:", "", 1)
                state = _decode_hash(redis_client.hgetall(key))
                state_slice_id = state.get("sliceId") or state.get("slice_id") or state.get("sliceId".lower())
                if _slice_id_matches(state_slice_id, normalized_slice_id) and entity_id not in entity_ids:
                    entity_ids.append(entity_id)
                if len(entity_ids) >= limit:
                    break
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis entity scan failed: %s", exc)
        return entity_ids

    def _read_entities(self, redis_client: Any, entity_ids: Sequence[str]) -> Dict[str, Any]:
        entities: Dict[str, Any] = {}
        for entity_id in entity_ids[:25]:
            state = _decode_hash(redis_client.hgetall(f"entity:{entity_id}"))
            if state:
                entities[entity_id] = _compact_entity_state(state)
        return entities

    def _read_aiops(self, redis_client: Any, entity_ids: Sequence[str]) -> Dict[str, Any]:
        aiops: Dict[str, Any] = {}
        for entity_id in entity_ids[:25]:
            per_entity = {}
            for name, prefix in AIOPS_PREFIXES.items():
                state = _decode_hash(redis_client.hgetall(f"{prefix}:{entity_id}"))
                if state:
                    per_entity[name] = _compact_aiops_state(state)
            if per_entity:
                aiops[entity_id] = per_entity
        return aiops

    def _read_cross_domain(self, redis_client: Any) -> Dict[str, Any]:
        values = {}
        for key in SCALAR_REDIS_KEYS:
            values[key] = decode_redis_value(redis_client.get(key))
        return values

    def _read_recent_events(
        self,
        redis_client: Any,
        slice_id: str,
        entity_ids: Sequence[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        recent: Dict[str, List[Dict[str, Any]]] = {}
        for name, stream in EVENT_STREAMS.items():
            events = []
            for message_id, fields in _xrevrange(redis_client, stream, count=30):
                event = _extract_stream_event(fields)
                if not isinstance(event, dict):
                    continue
                if not _event_matches(event, slice_id, entity_ids):
                    continue
                compact = _compact_event(event)
                compact["stream_id"] = message_id
                events.append(compact)
                if len(events) >= 5:
                    break
            recent[name] = events
        return recent

    @staticmethod
    def _error_payload(
        slice_id: str,
        entity_ids: Sequence[str],
        message: str,
        warnings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "status": "error",
            "source": "redis",
            "slice_id": slice_id or None,
            "entity_ids": list(entity_ids),
            "error": {"message": message or "Redis state query failed."},
            "active_faults": [],
            "entities": {},
            "aiops": {},
            "cross_domain": {},
            "recent_events": {},
        }
        if warnings:
            payload["warnings"] = warnings
        return payload


def fetch_influx_kpis_raw(
    slice_id: str = "",
    time_range: Any = None,
    domain: Optional[str] = None,
    entity_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    slice_type: Optional[str] = None,
    query_parameters: Any = None,
) -> Dict[str, Any]:
    return InfluxTelemetryClient().fetch_kpis(
        slice_id=slice_id,
        time_range=time_range,
        domain=domain,
        entity_id=entity_id,
        entity_type=entity_type,
        slice_type=slice_type,
        query_parameters=query_parameters,
    )


def fetch_redis_state_raw(
    slice_id: str = "",
    entity_ids: Optional[Sequence[str]] = None,
    query_parameters: Any = None,
) -> Dict[str, Any]:
    return RedisStateClient().fetch_state(
        slice_id=slice_id,
        entity_ids=entity_ids,
        query_parameters=query_parameters,
    )


def normalize_filters(
    slice_id: str = "",
    domain: Optional[str] = None,
    entity_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    slice_type: Optional[str] = None,
    query_parameters: Any = None,
) -> Tuple[Dict[str, Any], List[str]]:
    params = _normalize_query_parameters(query_parameters)
    warnings: List[str] = []
    raw_slice_id = _first_non_empty(slice_id, params.get("slice_id"), params.get("sliceId"))
    raw_domain = _first_non_empty(domain, params.get("domain"))
    raw_entity_id = _first_non_empty(entity_id, params.get("entity_id"), params.get("entityId"))
    raw_entity_type = _first_non_empty(entity_type, params.get("entity_type"), params.get("entityType"))
    raw_slice_type = _first_non_empty(slice_type, params.get("slice_type"), params.get("sliceType"))

    filters: Dict[str, Any] = {}
    if raw_slice_id:
        normalized_slice_id = _normalize_slice_token(raw_slice_id)
        if normalized_slice_id:
            filters["slice_id"] = normalized_slice_id
    if raw_entity_id:
        normalized_entity_id = str(raw_entity_id).strip().strip("`'\"")
        if normalized_entity_id:
            filters["entity_id"] = normalized_entity_id

    if raw_domain:
        normalized_domain = str(raw_domain).strip().lower()
        if normalized_domain in VALID_DOMAINS:
            filters["domain"] = normalized_domain
        else:
            warnings.append(f"Ignored invalid domain '{raw_domain}'.")

    if raw_entity_type:
        normalized_entity_type = str(raw_entity_type).strip()
        if normalized_entity_type in VALID_ENTITY_TYPES:
            filters["entity_type"] = normalized_entity_type
        else:
            warnings.append(f"Ignored invalid entity_type '{raw_entity_type}'.")

    if raw_slice_type:
        normalized_slice_type = _normalize_slice_type(raw_slice_type)
        if normalized_slice_type:
            filters["slice_type"] = normalized_slice_type
        else:
            warnings.append(f"Ignored invalid slice_type '{raw_slice_type}'.")

    return filters, warnings


def normalize_time_range(time_range: Any = None, query_parameters: Any = None) -> Dict[str, str]:
    params = _normalize_query_parameters(query_parameters)
    candidate = time_range
    if candidate in (None, ""):
        candidate = params.get("time_range") or params.get("timeRange")
    if candidate in (None, ""):
        start = params.get("start")
        stop = params.get("stop")
        if start or stop:
            candidate = {"start": start or DEFAULT_TIME_RANGE["start"], "stop": stop or DEFAULT_TIME_RANGE["stop"]}

    if isinstance(candidate, str):
        text = candidate.strip()
        if not text:
            return dict(DEFAULT_TIME_RANGE)
        try:
            candidate = json.loads(text)
        except json.JSONDecodeError:
            return {"start": text, "stop": DEFAULT_TIME_RANGE["stop"]}

    if isinstance(candidate, dict):
        start = str(candidate.get("start") or DEFAULT_TIME_RANGE["start"]).strip()
        stop = str(candidate.get("stop") or DEFAULT_TIME_RANGE["stop"]).strip()
        return {
            "start": start or DEFAULT_TIME_RANGE["start"],
            "stop": stop or DEFAULT_TIME_RANGE["stop"],
        }

    return dict(DEFAULT_TIME_RANGE)


def decode_redis_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _normalize_query_parameters(query_parameters: Any) -> Dict[str, Any]:
    if query_parameters is None:
        return {}
    if isinstance(query_parameters, str):
        try:
            decoded = json.loads(query_parameters)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    if isinstance(query_parameters, dict):
        return dict(query_parameters)
    return {}


def _extract_entity_ids(query_parameters: Any) -> List[str]:
    params = _normalize_query_parameters(query_parameters)
    raw = params.get("entity_ids") or params.get("entityIds") or params.get("entity_id") or params.get("entityId")
    return _normalize_entity_ids(raw)


def _normalize_entity_ids(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        try:
            decoded = json.loads(value)
            if isinstance(decoded, list):
                return _normalize_entity_ids(decoded)
        except json.JSONDecodeError:
            pass
        candidates = re.split(r"[, ]+", value)
    elif isinstance(value, Sequence):
        candidates = value
    else:
        candidates = [value]

    result: List[str] = []
    for candidate in candidates:
        text = str(candidate).strip()
        if text and text not in result:
            result.append(text)
    return result[:25]


def _first_non_empty(*values: Any) -> Optional[Any]:
    for value in values:
        if value is None:
            continue
        if str(value).strip():
            return value
    return None


def _normalize_slice_type(value: Any) -> Optional[str]:
    text = str(value).strip()
    for valid in VALID_SLICE_TYPES:
        if text.lower() == valid.lower():
            return valid
    return None


def _flux_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _flux_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_TIME_RANGE["stop"]
    if text == "now()" or re.fullmatch(r"-\d+[smhdw]", text):
        return text
    return f'time(v: "{_flux_escape(text)}")'


def _timestamp_to_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def _clean_tag(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nil"}:
        return None
    return text


def _coerce_numeric(value: Any) -> Any:
    decoded = decode_redis_value(value)
    if isinstance(decoded, bool):
        return 1.0 if decoded else 0.0
    if isinstance(decoded, (int, float)):
        return decoded
    if isinstance(decoded, str):
        try:
            return float(decoded)
        except ValueError:
            return decoded
    return decoded


def _decode_hash(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    return {str(key): decode_redis_value(value) for key, value in dict(raw).items()}


def _split_entities(value: Any) -> List[str]:
    decoded = decode_redis_value(value)
    if decoded is None:
        return []
    if isinstance(decoded, list):
        return [str(item).strip() for item in decoded if str(item).strip()]
    if isinstance(decoded, str):
        return [item.strip() for item in decoded.split(",") if item.strip()]
    return [str(decoded)]


def _fault_matches(record: Dict[str, Any], slice_id: str = "", entity_ids: Optional[Sequence[str]] = None) -> bool:
    normalized_slice_id = _normalize_token(slice_id)
    normalized_entity_ids = {_normalize_token(item) for item in _normalize_entity_ids(entity_ids)}
    normalized_entity_ids.discard("")

    if not normalized_slice_id and not normalized_entity_ids:
        return True

    affected_entities = [_normalize_token(item) for item in _split_entities(record.get("affected_entities"))]
    affected_text = ",".join(affected_entities)
    if normalized_slice_id and (
        normalized_slice_id in affected_entities
        or _normalize_token(f"slice:{normalized_slice_id}") in affected_entities
        or normalized_slice_id in affected_text
    ):
        return True

    if normalized_entity_ids and normalized_entity_ids.intersection(set(affected_entities)):
        return True

    return False


def _truthy(value: Any) -> bool:
    decoded = decode_redis_value(value)
    if isinstance(decoded, bool):
        return decoded
    if isinstance(decoded, (int, float)):
        return decoded > 0
    if isinstance(decoded, str):
        return decoded.strip().lower() in {"1", "true", "yes", "active"}
    return bool(decoded)


def _compact_fault(fault: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "fault_id": fault.get("fault_id"),
        "fault_type": fault.get("fault_type"),
        "start_time": fault.get("start_time"),
        "activated_at": fault.get("activated_at"),
        "duration_sec": fault.get("duration_sec"),
        "affected_entities": _split_entities(fault.get("affected_entities")),
        "severity": _coerce_numeric(fault.get("severity")),
        "scenario_id": fault.get("scenario_id"),
        "active_count": _coerce_numeric(fault.get("active_count")),
        "active": _truthy(fault.get("active", True)),
    }


def _entities_from_faults(faults: Sequence[Dict[str, Any]]) -> List[str]:
    entity_ids: List[str] = []
    for fault in faults:
        for entity in _split_entities(fault.get("affected_entities")):
            if entity.startswith("slice:"):
                continue
            if entity and entity not in entity_ids:
                entity_ids.append(entity)
            if len(entity_ids) >= 25:
                return entity_ids
    return entity_ids


def _compact_entity_state(state: Dict[str, Any]) -> Dict[str, Any]:
    keep = (
        "entityId",
        "entityType",
        "domain",
        "sliceId",
        "sliceType",
        "healthScore",
        "congestionScore",
        "misroutingScore",
        "severity",
        "lastUpdated",
        "scenarioId",
        "kpis",
        "aiopsCongestionScore",
        "aiopsCongestionPrediction",
        "aiopsCongestionSeverity",
        "aiopsCongestionUpdatedAt",
        "aiopsSliceClassification",
        "aiopsSliceClassificationConfidence",
        "aiopsSliceClassificationSeverity",
        "aiopsSliceClassificationUpdatedAt",
        "aiopsSlaRiskScore",
        "aiopsSlaPrediction",
        "aiopsSlaSeverity",
        "aiopsSlaUpdatedAt",
    )
    compact = {key: state.get(key) for key in keep if key in state}
    if isinstance(compact.get("kpis"), dict):
        compact["kpis"] = dict(list(compact["kpis"].items())[:20])
    return compact


def _compact_aiops_state(state: Dict[str, Any]) -> Dict[str, Any]:
    compact = {
        "eventId": state.get("eventId"),
        "timestamp": state.get("timestamp"),
        "service": state.get("service"),
        "siteId": state.get("siteId"),
        "sliceId": state.get("sliceId"),
        "entityId": state.get("entityId"),
        "entityType": state.get("entityType"),
        "severity": _coerce_numeric(state.get("severity")),
        "score": _coerce_numeric(state.get("score")),
        "prediction": state.get("prediction"),
        "modelVersion": state.get("modelVersion"),
        "sourceEventId": state.get("sourceEventId"),
    }
    details = state.get("details")
    if isinstance(details, dict):
        compact["details"] = dict(list(details.items())[:10])
    return {key: value for key, value in compact.items() if value is not None}


def _xrevrange(redis_client: Any, stream: str, count: int) -> List[Tuple[str, Dict[str, Any]]]:
    try:
        return redis_client.xrevrange(stream, count=count) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read Redis stream %s: %s", stream, exc)
        return []


def _extract_stream_event(fields: Dict[str, Any]) -> Any:
    decoded_fields = _decode_hash(fields)
    event = decoded_fields.get("event")
    return decode_redis_value(event)


def _event_matches(event: Dict[str, Any], slice_id: str, entity_ids: Sequence[str]) -> bool:
    normalized_slice_id = _normalize_token(slice_id)
    normalized_entity_ids = {_normalize_token(item) for item in _normalize_entity_ids(entity_ids)}
    normalized_entity_ids.discard("")
    if not normalized_slice_id and not normalized_entity_ids:
        return True
    event_slice_id = event.get("sliceId") or event.get("slice_id")
    event_entity_id = _normalize_token(event.get("entityId") or event.get("entity_id"))
    return (
        bool(normalized_slice_id and _slice_id_matches(event_slice_id, normalized_slice_id))
        or bool(event_entity_id and event_entity_id in normalized_entity_ids)
    )


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _slice_id_variants(value: Any) -> List[str]:
    token = _normalize_slice_token(value)
    if not token:
        return []

    variants: List[str] = []

    def _add(candidate: str) -> None:
        clean = _normalize_token(candidate)
        if clean and clean not in variants:
            variants.append(clean)

    _add(token)

    if token.startswith("slice:"):
        token = token.split("slice:", 1)[1]
        _add(token)

    if token.startswith("slice-"):
        _add(token[len("slice-"):])
    else:
        _add(f"slice-{token}")

    return variants


def _slice_id_matches(candidate: Any, requested: Any) -> bool:
    requested_variants = set(_slice_id_variants(requested))
    if not requested_variants:
        return True

    candidate_text = _normalize_slice_token(candidate)
    if not candidate_text:
        return False

    candidate_variants = set(_slice_id_variants(candidate_text))
    if requested_variants.intersection(candidate_variants):
        return True

    return any(variant in candidate_text for variant in requested_variants)


def _normalize_slice_token(value: Any) -> str:
    token = _normalize_token(value).strip("`'\"")
    token = re.sub(r"[?!.,;:]+$", "", token).strip()
    return token


def _compact_event(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: event.get(key)
        for key in (
            "eventId",
            "timestamp",
            "service",
            "siteId",
            "sliceId",
            "entityId",
            "entityType",
            "severity",
            "score",
            "prediction",
            "modelVersion",
            "sourceEventId",
        )
        if event.get(key) is not None
    }


def _scrub_secret(message: str, secret: Optional[str]) -> str:
    if not message:
        return ""
    scrubbed = message
    if secret:
        scrubbed = scrubbed.replace(secret, "[redacted]")
    return scrubbed
