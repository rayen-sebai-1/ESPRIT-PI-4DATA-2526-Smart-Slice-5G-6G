#!/usr/bin/env python3
"""Provision Smart Slice Kibana data view, visualizations, and dashboard."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DATA_VIEW_ID = "smart-slice-predictions-dv"
DASHBOARD_ID = "smart-slice-aiops-observability"

VIZ_IDS = {
    "line": "smart-slice-predictions-over-time",
    "pie": "smart-slice-prediction-distribution",
    "bar": "smart-slice-predictions-by-service",
    "count": "smart-slice-total-predictions",
    "avg_confidence": "smart-slice-avg-confidence",
}


def _request_json(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=body, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("kbn-xsrf", "true")

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed ({exc.code}): {details}") from exc


def _search_source_json() -> str:
    return json.dumps(
        {
            "query": {"query": "", "language": "kuery"},
            "filter": [],
            "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
        },
        separators=(",", ":"),
    )


def _build_visualization_payload(title: str, vis_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "attributes": {
            "title": title,
            "description": "",
            "visState": json.dumps(vis_state, separators=(",", ":")),
            "uiStateJSON": "{}",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": _search_source_json(),
            },
        },
        "references": [
            {
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern",
                "id": DATA_VIEW_ID,
            }
        ],
    }


def _build_dashboard_payload() -> dict[str, Any]:
    panels = [
        {
            "version": "8.13.4",
            "type": "visualization",
            "panelIndex": "1",
            "panelRefName": "panel_0",
            "gridData": {"x": 0, "y": 0, "w": 8, "h": 7, "i": "1"},
            "embeddableConfig": {},
        },
        {
            "version": "8.13.4",
            "type": "visualization",
            "panelIndex": "2",
            "panelRefName": "panel_1",
            "gridData": {"x": 8, "y": 0, "w": 8, "h": 7, "i": "2"},
            "embeddableConfig": {},
        },
        {
            "version": "8.13.4",
            "type": "visualization",
            "panelIndex": "3",
            "panelRefName": "panel_2",
            "gridData": {"x": 16, "y": 0, "w": 8, "h": 14, "i": "3"},
            "embeddableConfig": {},
        },
        {
            "version": "8.13.4",
            "type": "visualization",
            "panelIndex": "4",
            "panelRefName": "panel_3",
            "gridData": {"x": 0, "y": 7, "w": 16, "h": 14, "i": "4"},
            "embeddableConfig": {},
        },
        {
            "version": "8.13.4",
            "type": "visualization",
            "panelIndex": "5",
            "panelRefName": "panel_4",
            "gridData": {"x": 0, "y": 21, "w": 24, "h": 14, "i": "5"},
            "embeddableConfig": {},
        },
    ]

    return {
        "attributes": {
            "title": "Smart Slice AIOps Observability",
            "description": "Production-ready prediction monitoring dashboard for 5G/6G Smart Slice.",
            "hits": 0,
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "panelsJSON": json.dumps(panels, separators=(",", ":")),
            "timeRestore": False,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(
                    {
                        "query": {"query": "", "language": "kuery"},
                        "filter": [],
                    },
                    separators=(",", ":"),
                )
            },
        },
        "references": [
            {"name": "panel_0", "type": "visualization", "id": VIZ_IDS["count"]},
            {"name": "panel_1", "type": "visualization", "id": VIZ_IDS["avg_confidence"]},
            {"name": "panel_2", "type": "visualization", "id": VIZ_IDS["pie"]},
            {"name": "panel_3", "type": "visualization", "id": VIZ_IDS["line"]},
            {"name": "panel_4", "type": "visualization", "id": VIZ_IDS["bar"]},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Smart Slice Kibana observability objects.")
    parser.add_argument("--kibana-url", default="http://localhost:5601", help="Kibana base URL.")
    parser.add_argument(
        "--index-pattern",
        default="smart-slice-predictions*",
        help="Kibana data view pattern.",
    )
    parser.add_argument(
        "--prediction-field",
        default="ml.prediction.keyword",
        help="Field used for prediction distribution visualizations.",
    )
    parser.add_argument(
        "--service-field",
        default="service.name.keyword",
        help="Field used for service breakdown visualizations.",
    )
    parser.add_argument(
        "--confidence-field",
        default="ml.confidence",
        help="Field used for confidence metric.",
    )
    args = parser.parse_args()

    print("Creating/updating data view...")
    data_view_payload = {
        "attributes": {
            "title": args.index_pattern,
            "timeFieldName": "@timestamp",
        }
    }
    _request_json(
        "POST",
        args.kibana_url,
        f"/api/saved_objects/index-pattern/{DATA_VIEW_ID}?overwrite=true",
        data_view_payload,
    )

    line_vis_state = {
        "title": "Predictions Over Time",
        "type": "line",
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
            {
                "id": "2",
                "enabled": True,
                "type": "date_histogram",
                "schema": "segment",
                "params": {
                    "field": "@timestamp",
                    "timeRange": {"from": "now-24h", "to": "now"},
                    "useNormalizedEsInterval": True,
                    "scaleMetricValues": False,
                    "interval": "auto",
                    "drop_partials": False,
                    "min_doc_count": 1,
                    "extended_bounds": {},
                },
            },
            {
                "id": "3",
                "enabled": True,
                "type": "terms",
                "schema": "group",
                "params": {
                    "field": args.prediction_field,
                    "size": 10,
                    "order": "desc",
                    "orderBy": "1",
                    "otherBucket": False,
                    "missingBucket": False,
                },
            },
        ],
        "params": {
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "times": [],
            "categoryAxes": [
                {
                    "id": "CategoryAxis-1",
                    "type": "category",
                    "position": "bottom",
                    "show": True,
                    "labels": {"show": True, "truncate": 100},
                    "title": {},
                }
            ],
            "valueAxes": [
                {
                    "id": "ValueAxis-1",
                    "name": "LeftAxis-1",
                    "type": "value",
                    "position": "left",
                    "show": True,
                    "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                    "title": {"text": "Predictions"},
                }
            ],
            "seriesParams": [
                {
                    "show": True,
                    "type": "line",
                    "mode": "normal",
                    "data": {"id": "1", "label": "Count"},
                    "valueAxis": "ValueAxis-1",
                    "drawLinesBetweenPoints": True,
                    "showCircles": True,
                }
            ],
            "grid": {"categoryLines": False, "style": {"color": "#eee"}},
        },
    }

    pie_vis_state = {
        "title": "Prediction Distribution",
        "type": "pie",
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
            {
                "id": "2",
                "enabled": True,
                "type": "terms",
                "schema": "segment",
                "params": {
                    "field": args.prediction_field,
                    "size": 10,
                    "order": "desc",
                    "orderBy": "1",
                    "otherBucket": False,
                    "missingBucket": False,
                },
            },
        ],
        "params": {
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "isDonut": True,
            "labels": {"show": True, "values": True, "last_level": True, "truncate": 100},
        },
    }

    bar_vis_state = {
        "title": "Predictions Per Service",
        "type": "histogram",
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
            {
                "id": "2",
                "enabled": True,
                "type": "terms",
                "schema": "segment",
                "params": {
                    "field": args.service_field,
                    "size": 10,
                    "order": "desc",
                    "orderBy": "1",
                    "otherBucket": False,
                    "missingBucket": False,
                },
            },
        ],
        "params": {
            "addTooltip": True,
            "addLegend": False,
            "legendPosition": "right",
            "categoryAxes": [
                {
                    "id": "CategoryAxis-1",
                    "type": "category",
                    "position": "bottom",
                    "show": True,
                    "labels": {"show": True, "truncate": 100, "rotate": 45},
                    "title": {"text": "service.name"},
                }
            ],
            "valueAxes": [
                {
                    "id": "ValueAxis-1",
                    "name": "LeftAxis-1",
                    "type": "value",
                    "position": "left",
                    "show": True,
                    "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                    "title": {"text": "Predictions"},
                }
            ],
            "seriesParams": [
                {
                    "show": True,
                    "type": "histogram",
                    "mode": "stacked",
                    "data": {"id": "1", "label": "Count"},
                    "valueAxis": "ValueAxis-1",
                    "drawLinesBetweenPoints": True,
                    "showCircles": True,
                }
            ],
        },
    }

    total_count_vis_state = {
        "title": "Total Predictions",
        "type": "metric",
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}}
        ],
        "params": {"fontSize": 48},
    }

    avg_confidence_vis_state = {
        "title": "Average Confidence",
        "type": "metric",
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "avg",
                "schema": "metric",
                "params": {"field": args.confidence_field},
            }
        ],
        "params": {"fontSize": 40},
    }

    print("Creating/updating visualizations...")
    _request_json(
        "POST",
        args.kibana_url,
        f"/api/saved_objects/visualization/{VIZ_IDS['line']}?overwrite=true",
        _build_visualization_payload("Predictions Over Time", line_vis_state),
    )
    _request_json(
        "POST",
        args.kibana_url,
        f"/api/saved_objects/visualization/{VIZ_IDS['pie']}?overwrite=true",
        _build_visualization_payload("Prediction Distribution", pie_vis_state),
    )
    _request_json(
        "POST",
        args.kibana_url,
        f"/api/saved_objects/visualization/{VIZ_IDS['bar']}?overwrite=true",
        _build_visualization_payload("Predictions Per Service", bar_vis_state),
    )
    _request_json(
        "POST",
        args.kibana_url,
        f"/api/saved_objects/visualization/{VIZ_IDS['count']}?overwrite=true",
        _build_visualization_payload("Total Predictions", total_count_vis_state),
    )
    _request_json(
        "POST",
        args.kibana_url,
        f"/api/saved_objects/visualization/{VIZ_IDS['avg_confidence']}?overwrite=true",
        _build_visualization_payload("Average Confidence", avg_confidence_vis_state),
    )

    print("Creating/updating dashboard...")
    _request_json(
        "POST",
        args.kibana_url,
        f"/api/saved_objects/dashboard/{DASHBOARD_ID}?overwrite=true",
        _build_dashboard_payload(),
    )

    dashboard_url = f"{args.kibana_url.rstrip('/')}/app/dashboards#/view/{DASHBOARD_ID}"
    print("Dashboard provisioning completed.")
    print(f"Open dashboard: {dashboard_url}")
    print(
        "Recommended next step in Kibana: Add Controls for service.name.keyword, ml.model.keyword, and ml.prediction.keyword."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
