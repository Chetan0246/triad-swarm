"""Tests for structured JSON logging and OpenTelemetry/trace correlation."""

import json
import logging

from triad.core.logging import JSONLogFormatter, configure_logging, get_logger


def test_json_log_formatter():
    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="triad.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Production deployment active",
        args=(),
        exc_info=None,
    )
    record.trace_id = "trace-abc-123"
    record.job_id = "job-xyz-987"
    record.extra_fields = {"cluster": "prod-us-east-1"}

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["level"] == "INFO"
    assert data["logger"] == "triad.test"
    assert data["message"] == "Production deployment active"
    assert data["trace_id"] == "trace-abc-123"
    assert data["job_id"] == "job-xyz-987"
    assert data["cluster"] == "prod-us-east-1"
    assert "timestamp" in data


def test_configure_logging_json():
    logger = configure_logging(format_type="json", level="DEBUG")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) >= 1
    assert isinstance(logger.handlers[0].formatter, JSONLogFormatter)


def test_get_logger_prefix():
    logger = get_logger("orchestrator")
    assert logger.name == "triad.orchestrator"
