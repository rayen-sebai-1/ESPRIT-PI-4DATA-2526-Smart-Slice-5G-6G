"""Tests for Logstash-first monitoring delivery."""

from unittest.mock import MagicMock


def test_log_prediction_uses_logstash_when_enabled(monkeypatch):
    from src.monitoring import log_sender

    sent_request = {}

    def fake_urlopen(request, timeout):  # noqa: ANN001
        sent_request["url"] = request.full_url
        sent_request["timeout"] = timeout
        sent_request["content_type"] = request.headers["Content-type"]

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
                return False

        return _Response()

    monkeypatch.setenv("LOG_MONITORING_MODE", "logstash")
    monkeypatch.setenv("LOGSTASH_HTTP_URL", "http://logstash:8081/predictions")
    monkeypatch.setattr(log_sender.urllib.request, "urlopen", fake_urlopen)

    log_sender.log_prediction("sla_5g", {"x": 1}, "ok", 0.91, 12.5)

    assert sent_request["url"] == "http://logstash:8081/predictions"
    assert sent_request["timeout"] == 5
    assert sent_request["content_type"] == "application/json"


def test_log_prediction_falls_back_to_elasticsearch(monkeypatch):
    from src.monitoring import log_sender

    fake_client = MagicMock()
    fake_es_factory = MagicMock(return_value=fake_client)

    def fake_urlopen(request, timeout):  # noqa: ANN001
        raise OSError("logstash unavailable")

    monkeypatch.setenv("LOG_MONITORING_MODE", "logstash")
    monkeypatch.setenv("ES_HOST", "http://elasticsearch:9200")
    monkeypatch.setattr(log_sender.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(log_sender, "Elasticsearch", fake_es_factory)

    log_sender.log_prediction("slice_type_5g", {"x": 2}, "embb", 0.66, 9.0)

    fake_es_factory.assert_called_once_with("http://elasticsearch:9200")
    fake_client.index.assert_called_once()
