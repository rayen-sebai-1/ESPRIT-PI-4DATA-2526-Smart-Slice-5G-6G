"""Elasticsearch log-sender for Smart Slice prediction monitoring."""

import datetime
from typing import Any, Dict

from elasticsearch import Elasticsearch

ES_HOST = "http://localhost:9200"
INDEX_NAME = "smart-slice-predictions"


def log_prediction(
    model_name: str,
    input_data: Dict[str, Any],
    prediction: Any,
    confidence: float,
    latency_ms: float,
) -> None:
    """Index a prediction event to Elasticsearch.

    Args:
        model_name:  Name of the model that produced the prediction.
        input_data:  Raw input payload (dict).
        prediction:  Model output (any JSON-serialisable value).
        confidence:  Confidence / probability score in [0, 1].
        latency_ms:  Inference latency in milliseconds.
    """
    client = Elasticsearch(ES_HOST)
    document = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "model_name": model_name,
        "input_data": input_data,
        "prediction": prediction,
        "confidence": confidence,
        "latency_ms": latency_ms,
    }
    client.index(index=INDEX_NAME, body=document)
