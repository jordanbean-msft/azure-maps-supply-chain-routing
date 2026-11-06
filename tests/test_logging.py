import json
import logging
import sys

from template_repository.logging_config import JsonFormatter


def test_structured_logging_preserves_context_and_exception() -> None:
    try:
        raise ValueError("upstream unavailable")
    except ValueError:
        record = logging.LogRecord(
            "routing", logging.ERROR, __file__, 1, "failed %s", ("route",), None
        )
        record.request_id = "request-1"
        record.exc_info = sys.exc_info()
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "failed route"
    assert payload["request_id"] == "request-1"
    assert "ValueError: upstream unavailable" in payload["exception"]
