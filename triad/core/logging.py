"""Structured logging module for Triad Swarm with JSON and human-readable formats."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, Optional


class JSONLogFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects for Datadog, Loki, CloudWatch, and Vector."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject tracing metadata if present on the record
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id
        if hasattr(record, "span_id"):
            log_entry["span_id"] = record.span_id
        if hasattr(record, "job_id"):
            log_entry["job_id"] = record.job_id
        if hasattr(record, "slice_id"):
            log_entry["slice_id"] = record.slice_id

        # Inject extra attributes
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_entry.update(record.extra_fields)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def configure_logging(
    format_type: Optional[str] = None,
    level: str = "INFO",
) -> logging.Logger:
    """
    Configure application-wide logging.
    format_type: 'json' or 'text'. Defaults to env var TRIAD_LOG_FORMAT or 'text'.
    """
    fmt = format_type or os.getenv("TRIAD_LOG_FORMAT", "text").lower()
    log_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger("triad")
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers on re-configuration
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if fmt == "json":
        handler.setFormatter(JSONLogFormatter())
    else:
        text_fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(text_fmt)

    root_logger.addHandler(handler)
    return root_logger


def get_logger(name: str = "triad") -> logging.Logger:
    """Retrieve logger instance with Triad naming conventions."""
    if not name.startswith("triad"):
        name = f"triad.{name}"
    return logging.getLogger(name)
