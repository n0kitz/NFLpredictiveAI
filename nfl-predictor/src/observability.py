"""Lightweight observability: structured JSON logging + in-process request metrics.

No external deps. `setup_logging()` installs a JSON formatter; `metrics` is a
process-global counter updated by the API middleware and exposed at /api/metrics.
"""

import json
import logging
import threading
import time
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON for easy ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Attach a JSON handler to the root logger (idempotent, non-clobbering)."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)
    _configured = True


class Metrics:
    """Thread-safe process-global request counters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started = time.time()
        self.requests = 0
        self.errors_5xx = 0
        self.total_ms = 0.0
        self.max_ms = 0.0
        self.by_status: Dict[str, int] = {}

    def record_request(self, status: int, duration_ms: float) -> None:
        bucket = f"{status // 100}xx"
        with self._lock:
            self.requests += 1
            self.total_ms += duration_ms
            self.max_ms = max(self.max_ms, duration_ms)
            self.by_status[bucket] = self.by_status.get(bucket, 0) + 1
            if status >= 500:
                self.errors_5xx += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            avg = round(self.total_ms / self.requests, 2) if self.requests else 0.0
            return {
                "uptime_s": round(time.time() - self.started, 1),
                "requests": self.requests,
                "errors_5xx": self.errors_5xx,
                "avg_latency_ms": avg,
                "max_latency_ms": round(self.max_ms, 2),
                "by_status": dict(self.by_status),
            }


metrics = Metrics()
