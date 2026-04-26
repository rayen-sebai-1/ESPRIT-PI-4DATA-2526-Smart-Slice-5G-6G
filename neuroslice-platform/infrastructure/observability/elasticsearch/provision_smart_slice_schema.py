#!/usr/bin/env python3
"""Provision Elasticsearch schema and ILM policy for Smart Slice prediction observability."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_POLICY_FILE = BASE_DIR / "ilm-policy-smart-slice-predictions.json"
DEFAULT_TEMPLATE_FILE = BASE_DIR / "index-template-smart-slice-predictions.json"


def _request_json(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=body, method=method)
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed ({exc.code}): {details}") from exc


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Smart Slice Elasticsearch schema and ILM policy.")
    parser.add_argument("--es-url", default="http://localhost:9200", help="Elasticsearch base URL.")
    parser.add_argument(
        "--policy-name",
        default="smart-slice-predictions-ilm",
        help="ILM policy name to create/update.",
    )
    parser.add_argument(
        "--template-name",
        default="smart-slice-predictions-template",
        help="Index template name to create/update.",
    )
    parser.add_argument(
        "--index-name",
        default="smart-slice-predictions",
        help="Live index to update mapping/settings for.",
    )
    parser.add_argument(
        "--skip-live-index-update",
        action="store_true",
        help="Skip applying mapping/settings to the current live index.",
    )
    args = parser.parse_args()

    policy_payload = _load_json(DEFAULT_POLICY_FILE)
    template_payload = _load_json(DEFAULT_TEMPLATE_FILE)

    print(f"Applying ILM policy '{args.policy_name}' to {args.es_url}...")
    ilm_response = _request_json("PUT", args.es_url, f"/_ilm/policy/{args.policy_name}", policy_payload)
    print(json.dumps(ilm_response, indent=2))

    print(f"Applying index template '{args.template_name}'...")
    template_response = _request_json(
        "PUT",
        args.es_url,
        f"/_index_template/{args.template_name}",
        template_payload,
    )
    print(json.dumps(template_response, indent=2))

    if args.skip_live_index_update:
        print("Live index update skipped.")
        return 0

    mapping_properties = template_payload["template"]["mappings"]["properties"]
    mapping_update = {"properties": mapping_properties}

    print(f"Updating mapping for index '{args.index_name}'...")
    mapping_response = _request_json("PUT", args.es_url, f"/{args.index_name}/_mapping", mapping_update)
    print(json.dumps(mapping_response, indent=2))

    settings_update = {
        "index": {
            "refresh_interval": template_payload["template"]["settings"].get("refresh_interval", "5s"),
            "number_of_replicas": template_payload["template"]["settings"].get("number_of_replicas", 0),
            "lifecycle": {
                "name": args.policy_name,
            },
        }
    }

    print(f"Updating settings for index '{args.index_name}'...")
    settings_response = _request_json("PUT", args.es_url, f"/{args.index_name}/_settings", settings_update)
    print(json.dumps(settings_response, indent=2))

    print("Smart Slice Elasticsearch schema provisioning completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
