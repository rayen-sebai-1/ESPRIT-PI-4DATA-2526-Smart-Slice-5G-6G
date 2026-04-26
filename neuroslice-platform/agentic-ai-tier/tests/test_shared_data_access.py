from __future__ import annotations

from pathlib import Path
import sys
import unittest


AGENTIC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTIC_ROOT))

from shared.data_access import InfluxTelemetryClient, RedisStateClient, decode_redis_value
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


if __name__ == "__main__":
    unittest.main()

