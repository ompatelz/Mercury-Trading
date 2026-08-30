from __future__ import annotations

from collections import Counter
from threading import Lock


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counts: Counter[tuple[str, str]] = Counter()
        self._latency_ms: Counter[str] = Counter()

    def record_request(self, method: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._counts[(method, str(status_code))] += 1
            self._latency_ms[method] += int(duration_ms)

    def render_prometheus(self) -> str:
        with self._lock:
            lines = ["# TYPE mercury_http_requests_total counter"]
            lines.extend(
                f'mercury_http_requests_total{{method="{method}",status="{status}"}} {count}'
                for (method, status), count in sorted(self._counts.items())
            )
            lines.append("# TYPE mercury_http_request_latency_ms_total counter")
            lines.extend(
                f'mercury_http_request_latency_ms_total{{method="{method}"}} {total}'
                for method, total in sorted(self._latency_ms.items())
            )
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()
