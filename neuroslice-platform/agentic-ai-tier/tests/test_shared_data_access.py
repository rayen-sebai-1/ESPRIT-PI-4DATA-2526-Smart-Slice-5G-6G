from __future__ import annotations

from pathlib import Path
import sys
import unittest


AGENTIC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTIC_ROOT))

from shared.data_access import (
    InfluxTelemetryClient,
    RedisStateClient,
    _event_matches,
    _slice_id_matches,
    decode_redis_value,
    normalize_filters,
)
from shared.telemetry_summary import summarize_telemetry_records


class SharedDataAccessSmokeTests(unittest.TestCase):
    def test_clients_instantiate_without_services(self) -> None:
        influx = InfluxTelemetryClient()
        redis = RedisStateClient()

        self.assertEqual(influx.org, "neuroslice")
        self.assertEqual(influx.bucket, "telemetry")
        self.assertGreater(redis.port, 0)

    def test_decode_redis_value(self) -> None:
        self.assertEqual(decode_redis_value('{"score": 0.91, "active": true}'), {"score": 0.91, "active": True})
        self.assertEqual(decode_redis_value("[1, 2]"), [1, 2])
        self.assertEqual(decode_redis_value("plain-text"), "plain-text")

    def test_aggregation_summarizes_sample_records(self) -> None:
        records = [
            {
                "timestamp": "2026-04-26T10:00:00Z",
                "slice_id": "slice-001",
                "domain": "ran",
                "entity_id": "cell-01",
                "entity_type": "cell",
                "slice_type": "URLLC",
                "field": "kpi_packetLossPct",
                "value": 0.4,
            },
            {
                "timestamp": "2026-04-26T10:01:00Z",
                "slice_id": "slice-001",
                "domain": "ran",
                "entity_id": "cell-01",
                "entity_type": "cell",
                "slice_type": "URLLC",
                "field": "kpi_packetLossPct",
                "value": 2.4,
            },
            {
                "timestamp": "2026-04-26T10:02:00Z",
                "slice_id": "slice-001",
                "domain": "ran",
                "entity_id": "cell-01",
                "entity_type": "cell",
                "slice_type": "URLLC",
                "field": "kpi_packetLossPct",
                "value": 4.2,
            },
            {
                "timestamp": "2026-04-26T10:02:00Z",
                "slice_id": "slice-001",
                "domain": "ran",
                "entity_id": "cell-01",
                "entity_type": "cell",
                "slice_type": "URLLC",
                "field": "derived_congestionScore",
                "value": 0.86,
            },
        ]

        summary = summarize_telemetry_records(records)
        packet_loss = next(group for group in summary["groups"] if group["field"] == "kpi_packetLossPct")

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["summary"]["total_field_values_seen"], 4)
        self.assertEqual(packet_loss["breach_count"], 2)
        self.assertEqual(packet_loss["trend"], "increasing")
        self.assertLessEqual(len(packet_loss["samples"]), 3)
        self.assertEqual(summary["summary"]["top_anomalous_entities"][0]["entity_id"], "cell-01")

    def test_empty_telemetry_returns_compact_no_data(self) -> None:
        summary = summarize_telemetry_records([])

        self.assertEqual(summary["status"], "no_data")
        self.assertEqual(summary["summary"]["total_points_seen"], 0)
        self.assertEqual(summary["groups"], [])

    def test_slice_id_matching_accepts_prefixed_and_unprefixed(self) -> None:
        self.assertTrue(_slice_id_matches("slice-urllc-01-02", "urllc-01-02"))
        self.assertTrue(_slice_id_matches("urllc-01-02", "slice-urllc-01-02"))
        self.assertTrue(_slice_id_matches("slice:urllc-01-02", "urllc-01-02"))
        self.assertTrue(_slice_id_matches("slice-urllc-01-02", "slice-urllc-01-02?"))
        self.assertFalse(_slice_id_matches("slice-urllc-01-01", "urllc-01-02"))

    def test_event_match_uses_slice_variants(self) -> None:
        event = {"sliceId": "slice-urllc-01-02", "entityId": "cell-01-02"}
        self.assertTrue(_event_matches(event, "urllc-01-02", []))

    def test_flux_slice_filter_includes_variant_forms(self) -> None:
        client = InfluxTelemetryClient()
        flux = client._build_telemetry_flux(
            filters={"slice_id": "urllc-01-02"},
            time_range={"start": "-30m", "stop": "now()"},
        )
        self.assertIn('strings.toLower(v: r.slice_id) == "urllc-01-02"', flux)
        self.assertIn('strings.toLower(v: r.slice_id) == "slice-urllc-01-02"', flux)

    def test_normalize_filters_strips_slice_punctuation(self) -> None:
        filters, _ = normalize_filters(slice_id="slice-urllc-01-02?")
        self.assertEqual(filters.get("slice_id"), "slice-urllc-01-02")


if __name__ == "__main__":
    unittest.main()

